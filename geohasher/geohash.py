"""
A simple implementation of geohash based on:
    * http://en.wikipedia.org/wiki/Geohash
    * https://www.movable-type.co.uk/scripts/geohash.html
"""
from __future__ import division
from collections import namedtuple
from builtins import range
import decimal
import math

base32 = '0123456789bcdefghjkmnpqrstuvwxyz'


def _indexes(geohash):
    if not geohash:
        raise ValueError('Invalid geohash')

    for char in geohash:
        try:
            yield base32.index(char)
        except ValueError:
            raise ValueError('Invalid geohash')


def _fixedpoint(num, bound_max, bound_min):
    """
    Return given num with precision of 2 - log10(range)

    Params
    ------
    num: A number
    bound_max: max bound, e.g max latitude of a geohash cell(NE)
    bound_min: min bound, e.g min latitude of a geohash cell(SW)

    Returns
    -------
    A decimal
    """
    try:
        decimal.getcontext().prec = math.floor(2-math.log10(bound_max
                                                            - bound_min))
    except ValueError:
        decimal.getcontext().prec = 12
    return decimal.Decimal(num)


def bounds(geohash):
    """
    Returns SW/NE latitude/longitude bounds of a specified geohash.
        |      .| NE
        |    .  |
        |  .    |
     SW |.      |

     Params
     ----------
     geohash: string, cell that bounds are required of

     Returns
     -------
     Named Tuple of namedtuples Bounds(sw(lat, sw.lon), ne(lat, lon)). e.g.,
     southwest_lat = b.sw.lat
    """
    geohash = geohash.lower()

    even_bit = True
    lat_min = -90
    lat_max = 90
    lon_min = -180
    lon_max = 180

    # 5 bits for a char. So divide the decimal by power of 2, then AND 1
    # to get the binary bit - fast modulo operation.
    for index in _indexes(geohash):
        for n in range(4, -1, -1):
            bit = (index >> n) & 1
            if even_bit:
                # longitude
                lon_mid = (lon_min + lon_max) / 2
                if bit == 1:
                    lon_min = lon_mid
                else:
                    lon_max = lon_mid
            else:
                # latitude
                lat_mid = (lat_min + lat_max) / 2
                if bit == 1:
                    lat_min = lat_mid
                else:
                    lat_max = lat_mid
            even_bit = not even_bit

    SouthWest = namedtuple('SouthWest', ['lat', 'lon'])
    NorthEast = namedtuple('NorthEast', ['lat', 'lon'])
    sw = SouthWest(lat_min, lon_min)
    ne = NorthEast(lat_max, lon_max)
    Bounds = namedtuple('Bounds', ['sw', 'ne'])
    return Bounds(sw, ne)


def decode(geohash):
    """
    Decode geohash to latitude/longitude. Location is approximate centre of the
    cell to reasonable precision.

    Params
    ------
    geohash: string, cell that bounds are required of

    Returns
    ------
    Namedtuple (lat, lon) with lat, lon as properties
    """
    (lat_min, lon_min), (lat_max, lon_max) = bounds(geohash)

    lat = (lat_min + lat_max) / 2
    lon = (lon_min + lon_max) / 2

    lat = _fixedpoint(lat, lat_max, lat_min)
    lon = _fixedpoint(lon, lon_max, lon_min)
    Point = namedtuple('Point', ['lat', 'lon'])
    return Point(lat, lon)


def encode(lat, lon, precision):
    """
    Encode latitude, longitude to a geohash. Infers precision if not given.

    Params
    ------
    lat: latitude, a number or string that can be converted to decimal.
         Ideally pass a string to avoid floating point uncertainties.
         It will be converted to decimal.
    lon: longitude, a number or string that can be converted to decimal.
         Ideally pass a string to avoid floating point uncertainties.
         It will be converted to decimal.
    precision: integer, 1 to 12 represeting geohash levels upto 12.

    Returns
    -------
    geohash as string.
    """
    lat = decimal.Decimal(lat)
    lon = decimal.Decimal(lon)

    index = 0  # index into base32 map
    bit = 0   # each char holds 5 bits
    even_bit = True
    lat_min = -90
    lat_max = 90
    lon_min = -180
    lon_max = 180
    ghash = []

    while(len(ghash) < precision):
        if even_bit:
            # bisect E-W longitude
            lon_mid = (lon_min + lon_max) / 2
            if lon >= lon_mid:
                index = index * 2 + 1
                lon_min = lon_mid
            else:
                index = index * 2
                lon_max = lon_mid
        else:
            # bisect N-S latitude
            lat_mid = (lat_min + lat_max) / 2
            if lat >= lat_mid:
                index = index * 2 + 1
                lat_min = lat_mid
            else:
                index = index * 2
                lat_max = lat_mid
        even_bit = not even_bit

        bit += 1
        if bit == 5:
            # 5 bits gives a char in geohash. Start over
            ghash.append(base32[index])
            bit = 0
            index = 0

    return ''.join(ghash)


def adjacent(geohash, direction):
    """
    Determines adjacent cell in given direction.

    Params
    ------
    geohash: cell to which adjacent cell is required
    direction: direction from geohash, string, one of n, s, e, w

    Returns
    -------
    geohash of adjacent cell
    """
    if not geohash:
        raise ValueError('Invalid geohash')
    if direction not in ('nsew'):
        raise ValueError('Invalid direction')

    neighbour = {
        'n': ['p0r21436x8zb9dcf5h7kjnmqesgutwvy',
              'bc01fg45238967deuvhjyznpkmstqrwx'],
        's': ['14365h7k9dcfesgujnmqp0r2twvyx8zb',
              '238967debc01fg45kmstqrwxuvhjyznp'],
        'e': ['bc01fg45238967deuvhjyznpkmstqrwx',
              'p0r21436x8zb9dcf5h7kjnmqesgutwvy'],
        'w': ['238967debc01fg45kmstqrwxuvhjyznp',
              '14365h7k9dcfesgujnmqp0r2twvyx8zb'],
    }

    border = {
        'n': ['prxz',     'bcfguvyz'],
        's': ['028b',     '0145hjnp'],
        'e': ['bcfguvyz', 'prxz'],
        'w': ['0145hjnp', '028b'],
    }

    last_char = geohash[-1]
    parent = geohash[:-1]  # parent is hash without last char

    typ = len(geohash) % 2

    # check for edge-cases which don't share common prefix
    if last_char not in border[direction][typ] and parent:
        parent = adjacent(parent, direction)

    index = neighbour[direction][typ].index(last_char)
    return parent + base32[index]


def neighbours(geohash):
    """
    Returns all 8 adjacent cells to specified geohash

    | nw | n | ne |
    |  w | * | e  |
    | sw | s | se |

    Params
    ------
    geohash: string, geohash neighbours are required of

    Returns
    -------
    neighbours as namedtuple of geohashes with properties n,ne,e,se,s,sw,w,nw
    """
    n = adjacent(geohash, 'n')
    ne = adjacent(n, 'e')
    e = adjacent(geohash, 'e')
    s = adjacent(geohash, 's')
    se = adjacent(s, 'e')
    w = adjacent(geohash, 'w')
    sw = adjacent(s, 'w')
    nw = adjacent(n, 'w')
    Neighbours = namedtuple('Neighbours',
                            ['n', 'ne', 'e', 'se', 's', 'sw', 'w', 'nw'])
    return Neighbours(n, ne, e, se, s, sw, w, nw)