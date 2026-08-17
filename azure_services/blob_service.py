import logging

logger = logging.getLogger(__name__)


def upload_blob(container_client, file_path, blob_name):
    """Upload a file to Azure Blob Storage."""
    logger.info("Starting upload_blob for file '%s' as blob '%s'", file_path, blob_name)
    try:
        with open(file_path, "rb") as data:
            container_client.upload_blob(
                name=blob_name,
                data=data,
                overwrite=True,
            )

        logger.info(
            "Finished upload_blob successfully for blob '%s'",
            blob_name,
        )

    except FileNotFoundError:
        logger.error(
            "File not found: %s",
            file_path,
        )
        raise

    except Exception:
        logger.exception(
            "Failed to upload blob '%s'",
            blob_name,
        )
        raise


def download_blob(container_client, blob_name, download_path):
    """Download a blob to a local file."""
    logger.info("Starting download_blob for blob '%s' to '%s'", blob_name, download_path)
    try:
        blob_client = container_client.get_blob_client(
            blob_name
        )

        with open(download_path, "wb") as file:
            file.write(
                blob_client.download_blob().readall()
            )

        logger.info(
            "Finished download_blob successfully for blob '%s'",
            blob_name,
        )

    except Exception:
        logger.exception(
            "Failed to download blob '%s'",
            blob_name,
        )
        raise


def list_blobs(container_client):
    """List blobs in the configured container."""
    logger.info("Starting list_blobs")
    try:
        blobs = list(container_client.list_blobs())

        logger.info(
            "Finished list_blobs successfully (found %d blobs)",
            len(blobs),
        )

        return blobs

    except Exception:
        logger.exception("Failed to list blobs")
        raise


def delete_blob(container_client, blob_name):
    """Delete a blob from Azure Blob Storage."""
    logger.info("Starting delete_blob for blob '%s'", blob_name)
    try:
        blob_client = container_client.get_blob_client(
            blob_name
        )

        blob_client.delete_blob()

        logger.info(
            "Finished delete_blob successfully for blob '%s'",
            blob_name,
        )

    except Exception:
        logger.exception(
            "Failed to delete blob '%s'",
            blob_name,
        )
        raise