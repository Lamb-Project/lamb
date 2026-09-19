"""Decode credential images in memory only. Never log decoded payloads."""
from io import BytesIO
from urllib.parse import urlsplit, parse_qs
import warnings
from PIL import Image
from .connection import MoodleConnectionError

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 12_000_000


def decode_passport(data: bytes) -> str:
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise MoodleConnectionError('Select a QR image smaller than 5 MiB.')
    try:
        import zxingcpp
    except ImportError:
        from .policy import MoodleConfigurationError
        raise MoodleConfigurationError('QR image decoding is unavailable. Ask the administrator to install the backend QR dependency.') from None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as picture:
                if picture.format not in {'PNG', 'JPEG', 'WEBP'}:
                    raise MoodleConnectionError('Use a PNG, JPEG or WebP QR image.')
                if picture.width * picture.height > MAX_IMAGE_PIXELS:
                    raise MoodleConnectionError('Image is too large. Crop it to the QR code (maximum 12 megapixels).')
                image = picture.convert('RGB')
                codes = zxingcpp.read_barcodes(image, formats=zxingcpp.BarcodeFormat.QRCode)
    except MoodleConnectionError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise MoodleConnectionError('Image is too large. Crop it to the QR code.') from None
    except Exception:
        raise MoodleConnectionError('Cannot read this image. Select a PNG, JPEG or WebP QR image.') from None
    if not codes:
        raise MoodleConnectionError('No readable QR code found. Upload a clear image cropped around the complete QR code.')
    if len(codes) != 1:
        raise MoodleConnectionError('More than one QR code found. Crop the image to your Moodle login QR code.')
    passport = codes[0].text
    if len(passport) > 8192 or not passport.startswith('moodlemobile://'):
        raise MoodleConnectionError('This is not a Moodle mobile login QR code.')
    try:
        site = urlsplit(passport[len('moodlemobile://'):])
        params = parse_qs(site.query)
        if not params.get('qrlogin') or not params.get('userid'):
            raise MoodleConnectionError('This QR contains only a site address, not a login. In Moodle, use a QR code with automatic login.')
        if (len(params['qrlogin']) != 1 or len(params['userid']) != 1
                or not params['userid'][0].isdigit() or int(params['userid'][0]) < 1):
            raise ValueError()
    except MoodleConnectionError:
        raise
    except ValueError:
        raise MoodleConnectionError('Invalid Moodle login QR code. Generate a fresh one.') from None
    return passport
