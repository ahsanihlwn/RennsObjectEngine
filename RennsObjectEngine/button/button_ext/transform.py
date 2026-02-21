# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/. 
# 
# Author: @ahsanihlwn
# Copyright (c) 2026 @ahsanihlwn

import re

def parse_transform(value: str):
    """
    Support:
        scale(1.2)
        rotate(5deg)
        scale(1.1) rotate(5deg)
    """

    scale = 1.0
    rotate = 0.0

    if not value:
        return scale, rotate

    # scale(...)
    scale_match = re.search(r"scale\(([^)]+)\)", value)
    if scale_match:
        try:
            scale = float(scale_match.group(1))
        except:
            scale = 1.0

    # rotate(...)
    rotate_match = re.search(r"rotate\(([^)]+)\)", value)
    if rotate_match:
        raw = rotate_match.group(1).replace("deg", "")
        try:
            rotate = float(raw)
        except:
            rotate = 0.0

    return scale, rotate
