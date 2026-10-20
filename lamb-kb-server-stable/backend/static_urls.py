"""Join the configured public KB root with its static asset path."""

def static_url_prefix(home_url):
    return home_url.rstrip('/') + '/static'
