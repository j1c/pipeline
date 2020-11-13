import sys

import boto3


def s3_upload(
    s3_datapath,
    outDir,
    subject=None,
    session=None,
    access_key_id=None,
    secret_access_key=None,
    profile_name=None,
):
    if profile_name is not None:
        client = boto3.client("s3", profile_name=profile_name)
    elif (access_key_id is not None) & (secret_access_key is not None):
        client = boto3.client(
            "s3",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )
    else:
        msg = f"Profile name or access keys must be provided."
        raise ValueError(msg)

    bucket, remote = parse_path(s3_datapath)

    # check that bucket exists
    bkts = [bk["Name"] for bk in client.list_buckets()["Buckets"]]
    if bucket not in bkts:
        sys.exit(
            "Error: could not locate bucket. Available buckets: " + ", ".join(bkts)
        )

    # List all files and upload
    for root, _, files in os.walk(outDir):
        for file_ in files:
            if not "tmp/" in root:  # exclude things in the tmp/ folder
                if f"sub-{subject}/ses-{session}" in root:
                    print(f"Uploading: {os.path.join(root, file_)}")
                    spath = root[root.find("sub-") :]  # remove everything before /sub-*
                    client.upload_file(
                        os.path.join(root, file_),
                        bucket,
                        f"{remote}/{os.path.join(spath,file_)}",
                        ExtraArgs={"ACL": "public-read"},
                    )


def parse_path(s3_datapath):
    """
    Return bucket and prefix from full s3 path.

    Parameters
    ----------
    s3_datapath : str
        path to a bucket.
        Should be of the form s3://bucket/prefix/.

    Returns
    -------
    tuple
        bucket and prefix.
    """
    bucket_path = str(s3_datapath).split("//")[1]
    parts = bucket_path.split("/")
    bucket = parts[0].strip("/")
    prefix = "/".join(parts[1:])
    return bucket, prefix