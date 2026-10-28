HOME = 'salink:home:v1'
SALING_BAGI_INDEX = 'salink:saling-bagi:index:v1'


def invalidate_public_pages(cache):
    cache.delete_many((HOME, SALING_BAGI_INDEX))