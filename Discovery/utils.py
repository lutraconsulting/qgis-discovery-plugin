# -*- coding: utf-8 -*-

# Discovery Plugin
#
# Copyright (C) 2020 Lutra Consulting
# info@lutraconsulting.co.uk
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.


def is_number(s):
    """Return True if s is a number"""
    try:
        float(s)
        return True
    except ValueError:
        return False
    except TypeError:
        return False
