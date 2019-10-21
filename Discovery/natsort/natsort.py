# -*- coding: utf-8 -*-
"""
Along with ns_enum.py, this module contains all of the
natsort public API.

The majority of the "work" is defined in utils.py.
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import sys
from functools import partial
from operator import itemgetter

import natsort.compat.locale
from natsort import utils
from natsort.compat.py23 import py23_cmp, py23_str, u_format
from natsort.ns_enum import NS_DUMB, ns


@u_format
def decoder(encoding):
    """
    Return a function that can be used to decode bytes to unicode.

    Parameters
    ----------
    encoding : str
        The codec to use for decoding. This must be a valid unicode codec.

    Returns
    -------
    decode_function
        A function that takes a single argument and attempts to decode
        it using the supplied codec. Any `UnicodeErrors` are raised.
        If the argument was not of `bytes` type, it is simply returned
        as-is.

    See Also
    --------
    as_ascii
    as_utf8

    Examples
    --------

        >>> f = decoder('utf8')
        >>> f(b'bytes') == 'bytes'
        True
        >>> f(12345) == 12345
        True
        >>> # On Python 3, without decoder this would return [b'a10', b'a2']
        >>> natsorted([b'a10', b'a2'], key=decoder('utf8')) == [b'a2', b'a10']
        True
        >>> # On Python 3, without decoder this would raise a TypeError.
        >>> natsorted([b'a10', 'a2'], key=decoder('utf8')) == ['a2', b'a10']
        True

    """
    return partial(utils.do_decoding, encoding=encoding)


@u_format
def as_ascii(s):
    """
    Function to decode an input with the ASCII codec, or return as-is.

    Parameters
    ----------
    s : object

    Returns
    -------
    output
        If the input was of type `bytes`, the return value is a `str` decoded
        with the ASCII codec. Otherwise, the return value is identically the
        input.

    See Also
    --------
    decoder

    """
    return utils.do_decoding(s, "ascii")


@u_format
def as_utf8(s):
    """
    Function to decode an input with the UTF-8 codec, or return as-is.

    Parameters
    ----------
    s : object

    Returns
    -------
    output
        If the input was of type `bytes`, the return value is a `str` decoded
        with the UTF-8 codec. Otherwise, the return value is identically the
        input.

    See Also
    --------
    decoder

    """
    return utils.do_decoding(s, "utf-8")


@u_format
def natsort_keygen(key=None, alg=ns.DEFAULT):
    """
    Generate a key to sort strings and numbers naturally.

    This key is designed for use as the `key` argument to
    functions such as the `sorted` builtin.

    The user may customize the generated function with the
    arguments to `natsort_keygen`, including an optional
    `key` function.

    Parameters
    ----------
    key : callable, optional
        A key used to manipulate the input value before parsing for
        numbers. It is **not** applied recursively.
        It should accept a single argument and return a single value.

    alg : ns enum, optional
        This option is used to control which algorithm `natsort`
        uses when sorting. For details into these options, please see
        the :class:`ns` class documentation. The default is `ns.INT`.

    Returns
    -------
    out : function
        A function that parses input for natural sorting that is
        suitable for passing as the `key` argument to functions
        such as `sorted`.

    See Also
    --------
    natsorted
    natsort_key

    Examples
    --------
    `natsort_keygen` is a convenient way to create a custom key
    to sort lists in-place (for example).::

        >>> a = ['num5.10', 'num-3', 'num5.3', 'num2']
        >>> a.sort(key=natsort_keygen(alg=ns.REAL))
        >>> a
        [{u}'num-3', {u}'num2', {u}'num5.10', {u}'num5.3']

    """
    try:
        ns.DEFAULT | alg
    except TypeError:
        msg = "natsort_keygen: 'alg' argument must be from the enum 'ns'"
        raise ValueError(msg + ", got {}".format(py23_str(alg)))

    # Add the NS_DUMB option if the locale library is broken.
    if alg & ns.LOCALEALPHA and natsort.compat.locale.dumb_sort():
        alg |= NS_DUMB

    # Set some variables that will be passed to the factory functions
    if alg & ns.NUMAFTER:
        if alg & ns.LOCALEALPHA:
            sep = natsort.compat.locale.null_string_locale_max
        else:
            sep = natsort.compat.locale.null_string_max
        pre_sep = natsort.compat.locale.null_string_max
    else:
        if alg & ns.LOCALEALPHA:
            sep = natsort.compat.locale.null_string_locale
        else:
            sep = natsort.compat.locale.null_string
        pre_sep = natsort.compat.locale.null_string
    regex = utils.regex_chooser(alg)

    # Create the functions that will be used to split strings.
    input_transform = utils.input_string_transform_factory(alg)
    component_transform = utils.string_component_transform_factory(alg)
    final_transform = utils.final_data_transform_factory(alg, sep, pre_sep)

    # Create the high-level parsing functions for strings, bytes, and numbers.
    string_func = utils.parse_string_factory(
        alg, sep, regex.split, input_transform, component_transform, final_transform
    )
    if alg & ns.PATH:
        string_func = utils.parse_path_factory(string_func)
    bytes_func = utils.parse_bytes_factory(alg)
    num_func = utils.parse_number_factory(alg, sep, pre_sep)

    # Return the natsort key with the parsing path pre-chosen.
    return partial(
        utils.natsort_key,
        key=key,
        string_func=string_func,
        bytes_func=bytes_func,
        num_func=num_func,
    )


# Exposed for simplicity if one needs the default natsort key.
natsort_key = natsort_keygen()
natsort_key.__doc__ = """\
natsort_key(val)
The default natural sorting key.

This is the output of :func:`natsort_keygen` with default values.

See Also
--------
natsort_keygen

"""


@u_format
def natsorted(seq, key=None, reverse=False, alg=ns.DEFAULT):
    """
    Sorts an iterable naturally.

    Parameters
    ----------
    seq : iterable
        The input to sort.

    key : callable, optional
        A key used to determine how to sort each element of the iterable.
        It is **not** applied recursively.
        It should accept a single argument and return a single value.

    reverse : {{True, False}}, optional
        Return the list in reversed sorted order. The default is
        `False`.

    alg : ns enum, optional
        This option is used to control which algorithm `natsort`
        uses when sorting. For details into these options, please see
        the :class:`ns` class documentation. The default is `ns.INT`.

    Returns
    -------
    out: list
        The sorted input.

    See Also
    --------
    natsort_keygen : Generates the key that makes natural sorting possible.
    realsorted : A wrapper for ``natsorted(seq, alg=ns.REAL)``.
    humansorted : A wrapper for ``natsorted(seq, alg=ns.LOCALE)``.
    index_natsorted : Returns the sorted indexes from `natsorted`.

    Examples
    --------
    Use `natsorted` just like the builtin `sorted`::

        >>> a = ['num3', 'num5', 'num2']
        >>> natsorted(a)
        [{u}'num2', {u}'num3', {u}'num5']

    """
    key = natsort_keygen(key, alg)
    return sorted(seq, reverse=reverse, key=key)


@u_format
def humansorted(seq, key=None, reverse=False, alg=ns.DEFAULT):
    """
    Convenience function to properly sort non-numeric characters.

    This is a wrapper around ``natsorted(seq, alg=ns.LOCALE)``.

    Parameters
    ----------
    seq : iterable
        The input to sort.

    key : callable, optional
        A key used to determine how to sort each element of the sequence.
        It is **not** applied recursively.
        It should accept a single argument and return a single value.

    reverse : {{True, False}}, optional
        Return the list in reversed sorted order. The default is
        `False`.

    alg : ns enum, optional
        This option is used to control which algorithm `natsort`
        uses when sorting. For details into these options, please see
        the :class:`ns` class documentation. The default is `ns.LOCALE`.

    Returns
    -------
    out : list
        The sorted input.

    See Also
    --------
    index_humansorted : Returns the sorted indexes from `humansorted`.

    Notes
    -----
    Please read :ref:`locale_issues` before using `humansorted`.

    Examples
    --------
    Use `humansorted` just like the builtin `sorted`::

        >>> a = ['Apple', 'Banana', 'apple', 'banana']
        >>> natsorted(a)
        [{u}'Apple', {u}'Banana', {u}'apple', {u}'banana']
        >>> humansorted(a)
        [{u}'apple', {u}'Apple', {u}'banana', {u}'Banana']

    """
    return natsorted(seq, key, reverse, alg | ns.LOCALE)


@u_format
def realsorted(seq, key=None, reverse=False, alg=ns.DEFAULT):
    """
    Convenience function to properly sort signed floats.

    A signed float in a string could be "a-5.7". This is a wrapper around
    ``natsorted(seq, alg=ns.REAL)``.

    The behavior of :func:`realsorted` for `natsort` version >= 4.0.0
    was the default behavior of :func:`natsorted` for `natsort`
    version < 4.0.0.

    Parameters
    ----------
    seq : iterable
        The input to sort.

    key : callable, optional
        A key used to determine how to sort each element of the sequence.
        It is **not** applied recursively.
        It should accept a single argument and return a single value.

    reverse : {{True, False}}, optional
        Return the list in reversed sorted order. The default is
        `False`.

    alg : ns enum, optional
        This option is used to control which algorithm `natsort`
        uses when sorting. For details into these options, please see
        the :class:`ns` class documentation. The default is `ns.REAL`.

    Returns
    -------
    out : list
        The sorted input.

    See Also
    --------
    index_realsorted : Returns the sorted indexes from `realsorted`.

    Examples
    --------
    Use `realsorted` just like the builtin `sorted`::

        >>> a = ['num5.10', 'num-3', 'num5.3', 'num2']
        >>> natsorted(a)
        [{u}'num2', {u}'num5.3', {u}'num5.10', {u}'num-3']
        >>> realsorted(a)
        [{u}'num-3', {u}'num2', {u}'num5.10', {u}'num5.3']

    """
    return natsorted(seq, key, reverse, alg | ns.REAL)


@u_format
def index_natsorted(seq, key=None, reverse=False, alg=ns.DEFAULT):
    """
    Determine the list of the indexes used to sort the input sequence.

    Sorts a sequence naturally, but returns a list of sorted the
    indexes and not the sorted list itself. This list of indexes
    can be used to sort multiple lists by the sorted order of the
    given sequence.

    Parameters
    ----------
    seq : iterable
        The input to sort.

    key : callable, optional
        A key used to determine how to sort each element of the sequence.
        It is **not** applied recursively.
        It should accept a single argument and return a single value.

    reverse : {{True, False}}, optional
        Return the list in reversed sorted order. The default is
        `False`.

    alg : ns enum, optional
        This option is used to control which algorithm `natsort`
        uses when sorting. For details into these options, please see
        the :class:`ns` class documentation. The default is `ns.INT`.

    Returns
    -------
    out : tuple
        The ordered indexes of the input.

    See Also
    --------
    natsorted
    order_by_index

    Examples
    --------

    Use index_natsorted if you want to sort multiple lists by the
    sorted order of one list::

        >>> a = ['num3', 'num5', 'num2']
        >>> b = ['foo', 'bar', 'baz']
        >>> index = index_natsorted(a)
        >>> index
        [2, 0, 1]
        >>> # Sort both lists by the sort order of a
        >>> order_by_index(a, index)
        [{u}'num2', {u}'num3', {u}'num5']
        >>> order_by_index(b, index)
        [{u}'baz', {u}'foo', {u}'bar']

    """
    if key is None:
        newkey = itemgetter(1)
    else:

        def newkey(x):
            return key(itemgetter(1)(x))

    # Pair the index and sequence together, then sort by element
    index_seq_pair = [[x, y] for x, y in enumerate(seq)]
    index_seq_pair.sort(reverse=reverse, key=natsort_keygen(newkey, alg))
    return [x for x, _ in index_seq_pair]


@u_format
def index_humansorted(seq, key=None, reverse=False, alg=ns.DEFAULT):
    """
    This is a wrapper around ``index_natsorted(seq, alg=ns.LOCALE)``.

    Parameters
    ----------
    seq: iterable
        The input to sort.

    key: callable, optional
        A key used to determine how to sort each element of the sequence.
        It is **not** applied recursively.
        It should accept a single argument and return a single value.

    reverse : {{True, False}}, optional
        Return the list in reversed sorted order. The default is
        `False`.

    alg : ns enum, optional
        This option is used to control which algorithm `natsort`
        uses when sorting. For details into these options, please see
        the :class:`ns` class documentation. The default is `ns.LOCALE`.

    Returns
    -------
    out : tuple
        The ordered indexes of the input.

    See Also
    --------
    humansorted
    order_by_index

    Notes
    -----
    Please read :ref:`locale_issues` before using `humansorted`.

    Examples
    --------
    Use `index_humansorted` just like the builtin `sorted`::

        >>> a = ['Apple', 'Banana', 'apple', 'banana']
        >>> index_humansorted(a)
        [2, 0, 3, 1]

    """
    return index_natsorted(seq, key, reverse, alg | ns.LOCALE)


@u_format
def index_realsorted(seq, key=None, reverse=False, alg=ns.DEFAULT):
    """
    This is a wrapper around ``index_natsorted(seq, alg=ns.REAL)``.

    Parameters
    ----------
    seq: iterable
        The input to sort.

    key: callable, optional
        A key used to determine how to sort each element of the sequence.
        It is **not** applied recursively.
        It should accept a single argument and return a single value.

    reverse : {{True, False}}, optional
        Return the list in reversed sorted order. The default is
        `False`.

    alg : ns enum, optional
        This option is used to control which algorithm `natsort`
        uses when sorting. For details into these options, please see
        the :class:`ns` class documentation. The default is `ns.REAL`.

    Returns
    -------
    out : tuple
        The ordered indexes of the input.

    See Also
    --------
    realsorted
    order_by_index

    Examples
    --------
    Use `index_realsorted` just like the builtin `sorted`::

        >>> a = ['num5.10', 'num-3', 'num5.3', 'num2']
        >>> index_realsorted(a)
        [1, 3, 0, 2]

    """
    return index_natsorted(seq, key, reverse, alg | ns.REAL)


# noinspection PyShadowingBuiltins,PyUnresolvedReferences
@u_format
def order_by_index(seq, index, iter=False):
    """
    Order a given sequence by an index sequence.

    The output of `index_natsorted` is a
    sequence of integers (index) that correspond to how its input
    sequence **would** be sorted. The idea is that this index can
    be used to reorder multiple sequences by the sorted order of the
    first sequence. This function is a convenient wrapper to
    apply this ordering to a sequence.

    Parameters
    ----------
    seq : sequence
        The sequence to order.

    index : iterable
        The iterable that indicates how to order `seq`.
        It should be the same length as `seq` and consist
        of integers only.

    iter : {{True, False}}, optional
        If `True`, the ordered sequence is returned as a
        iterator; otherwise it is returned as a
        list. The default is `False`.

    Returns
    -------
    out : {{list, iterator}}
        The sequence ordered by `index`, as a `list` or as an
        iterator (depending on the value of `iter`).

    See Also
    --------
    index_natsorted
    index_humansorted
    index_realsorted

    Examples
    --------

    `order_by_index` is a convenience function that helps you apply
    the result of `index_natsorted`::

        >>> a = ['num3', 'num5', 'num2']
        >>> b = ['foo', 'bar', 'baz']
        >>> index = index_natsorted(a)
        >>> index
        [2, 0, 1]
        >>> # Sort both lists by the sort order of a
        >>> order_by_index(a, index)
        [{u}'num2', {u}'num3', {u}'num5']
        >>> order_by_index(b, index)
        [{u}'baz', {u}'foo', {u}'bar']

    """
    return (seq[i] for i in index) if iter else [seq[i] for i in index]


if float(sys.version[:3]) < 3:
    # pylint: disable=unused-variable
    # noinspection PyUnresolvedReferences,PyPep8Naming
    class natcmp(object):  # noqa: N801
        """
        Compare two objects using a key and an algorithm.

        Parameters
        ----------
        x : object
            First object to compare.

        y : object
            Second object to compare.

        alg : ns enum, optional
            This option is used to control which algorithm `natsort`
            uses when sorting. For details into these options, please see
            the :class:`ns` class documentation. The default is `ns.INT`.

        Returns
        -------
        out: int
            0 if x and y are equal, 1 if x > y, -1 if y > x.

        See Also
        --------
        natsort_keygen : Generates a key that makes natural sorting possible.

        Examples
        --------
        Use `natcmp` just like the builtin `cmp`::

            >>> one = 1
            >>> two = 2
            >>> natcmp(one, two)
            -1
        """

        cached_keys = {}

        def __new__(cls, x, y, alg=ns.DEFAULT):
            try:
                ns.DEFAULT | alg
            except TypeError:
                msg = "natsort_keygen: 'alg' argument must be from the enum 'ns'"
                raise ValueError(msg + ", got {}".format(py23_str(alg)))

            # Add the _DUMB option if the locale library is broken.
            if alg & ns.LOCALEALPHA and natsort.compat.locale.dumb_sort():
                alg |= NS_DUMB

            if alg not in cls.cached_keys:
                cls.cached_keys[alg] = natsort_keygen(alg=alg)

            return py23_cmp(cls.cached_keys[alg](x), cls.cached_keys[alg](y))
