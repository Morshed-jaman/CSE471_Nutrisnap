import cloudinary
import cloudinary.uploader
from flask import current_app


def _configure_cloudinary() -> None:
    cloud_name = current_app.config.get("CLOUDINARY_CLOUD_NAME")
    api_key = current_app.config.get("CLOUDINARY_API_KEY")
    api_secret = current_app.config.get("CLOUDINARY_API_SECRET")

    if not cloud_name or not api_key or not api_secret:
        raise RuntimeError(
            "Cloudinary credentials are missing. Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET in .env."
        )

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
        #secure=True,

    )
# configure cloudinary then delete the image using its public id

def upload_image(file_path: str, folder: str = "meal_logs") -> tuple[str, str | None]:
    _configure_cloudinary()
    result = cloudinary.uploader.upload(file_path, folder=folder)
    secure_url = result.get("secure_url")
    public_id = result.get("public_id")
    if not secure_url:
        raise ValueError("Cloudinary upload failed: secure_url missing.")
    return secure_url, public_id


def delete_image(public_id: str | None) -> None:
    if not public_id:
        return
    _configure_cloudinary()
    cloudinary.uploader.destroy(public_id)
