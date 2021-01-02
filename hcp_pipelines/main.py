import shutil
import subprocess
from argparse import ArgumentParser
from pathlib import Path

from hcp2bids import convert, get_data

from .utils import s3_upload


def run(cmd):
    """
    Wrapper on `subprocess.run`.
    Print the command.
    Execute a command string on the shell (on bash).
    Exists so that the shell prints out commands as m2g calls them.

    Parameters
    ----------
    cmd : str
        Command to be sent to the shell.
    """
    print(f"Running shell command: {cmd}")
    subprocess.run(cmd, shell=True, check=True)


def main():
    parser = ArgumentParser(
        description="This is an end-to-end connectome estimation pipeline from multishell images."
    )
    parser.add_argument("--skip_dmriprep", action="store_true")
    parser.add_argument("--skip_download", action="store_true")
    parser.add_argument("--skip_m2g", action="store_true")
    parser.add_argument("--only_dmriprep", action="store_true")
    parser.add_argument(
        "--push_location",
        action="store",
        help="Name of folder on s3 to push output data to, if the folder does not exist, it will be created."
        "Format the location as `s3://<bucket>/<path>`",
        default=None,
    )
    parser.add_argument(
        "--remove_work_dir",
        action="store_true",
        help="Remove the work directory from dmriprep outputs if true.",
    )
    parser.add_argument(
        "--exclude_download",
        action="store",
        help="Keywords used to skip files in downloads",
        nargs="+",
    )
    parser.add_argument(
        "--n_cpus",
        action="store",
        type=int,
        default=8,
        help="Maximum number of threads across all processes. Minimum required is 8.",
    )
    parser.add_argument(
        "--mem_gb",
        action="store",
        default=16,
        type=int,
        help="Upper bound memory limit for dMRIPrep processes. Minimum required is 16 GB.",
    )
    parser.add_argument(
        "--participant_label",
        help="""The label(s) of the
        participant(s) that should be analyzed. The label
        corresponds to sub-<participant_label> from the BIDS
        spec (so it does not include "sub-"). If this
        parameter is not provided all subjects should be
        analyzed. Multiple participants can be specified
        with a space separated list.""",
    )
    parser.add_argument(
        "--denoise_strategy",
        action="store",
        default="mppca",
        help="Denoising strategy. Choices include: mppca, nlmeans, localpca, and nlsam",
    )
    parser.add_argument(
        "--mod",
        action="store",
        help="Deterministic (det) or probabilistic (prob) tracking. Default is det.",
        default="det",
    )
    parser.add_argument(
        "--filtering_type",
        action="store",
        help="Tracking approach: local, particle. Default is local.",
        default="local",
    )
    parser.add_argument(
        "--diffusion_model",
        action="store",
        help="Diffusion model: csd or csa. Default is csa.",
        default="csa",
    )
    parser.add_argument(
        "--seeds",
        action="store",
        help="Seeding density for tractography. Default is 20.",
        default=20,
    )
    parser.add_argument(
        "--parcellation",
        action="store",
        help="The parcellation(s) being analyzed. Multiple parcellations can be provided with a space separated list.",
        nargs="+",
        default=None,
    )
    parser.add_argument(
        "--hcp_key",
        action="store",
        help="Credentials for HCP bucket in form of (public, secret) key.",
        nargs="+",
        default=None,
    )
    parser.add_argument(
        "--s3_key",
        action="store",
        help="Credentials for s3 upload bucket in form of (public, secret) key.",
        nargs="+",
        default=None,
    )
    args = parser.parse_args()

    if len(args.hcp_key) != 2:
        raise ValueError("--hcp_key must have two parameters.")

    if args.push_location:
        if len(args.hcp_key) != 2:
            raise ValueError("--s3_key must have two parameters.")

    if not args.skip_download:
        # Get the data and convert to bids
        print("Downloading data...\n")
        get_data(
            output_path="/input",
            subjects=args.participant_label,
            access_key_id=args.hcp_key[0],
            secret_access_key=args.hcp_key[1],
            exclude_list=args.exclude_download,
        )
        convert(
            input_path="/input",
            output_path="/input",
            include_ses=True,
        )

    if not args.skip_dmriprep:
        # Run dmriprep
        print("Running dmriprep...\n")
        cmd = f"dmriprep /input /output participant -w /work_dir -s 1 \
            --denoise_strategy {args.denoise_strategy} \
            --participant_label {args.participant_label} \
            --nprocs {args.n_cpus} --omp_nthreads {args.n_cpus} --mem_gb {args.mem_gb} "
        run(cmd)

        # Skip all other steps. Only useful for debugging.
        if args.only_dmriprep:
            return 0

        # Rename files
        input_dir = f"/input/sub-{args.participant_label}/ses-1/dwi/"
        shutil.rmtree(input_dir)
        shutil.copytree(
            f"/output/sub-{args.participant_label}/ses-1/dwi/",
            f"/input/sub-{args.participant_label}/ses-1/dwi/",
        )
        shutil.rmtree("/output/", ignore_errors=True)
        input_dir = Path(input_dir)

        # Make output dir per m2g spec
        m2g_path = Path(f"/output/sub-{args.participant_label}/ses-1/dwi/preproc/")
        m2g_path.mkdir(parents=True, exist_ok=True)

        files = list(input_dir.glob("*.*"))
        for file in files:
            if not "final" in file.name:
                file.unlink()
            else:
                parent = file.parent
                bids_name = f"sub-{args.participant_label}_ses-1_run-1_dwi"
                suffix = file.suffix
                if suffix == ".gz":
                    suffix = ".nii.gz"

                new_name = parent / (bids_name + suffix)
                file.rename(new_name)

                if suffix == ".nii.gz":
                    eddy_file = m2g_path / "eddy_corrected_data.nii.gz"
                    shutil.copyfile(str(new_name.absolute()), str(eddy_file.absolute()))

        # Delete work dir
        if args.remove_work_dir:
            shutil.rmtree("/work_dir", ignore_errors=True)

    # Run m2g
    if not args.skip_m2g:
        cmd = f"m2g_bids --participant_label {args.participant_label} --session_label 1\
            --pipeline dwi --skipeddy --voxelsize 1mm\
            --parcellation {' '.join(args.parcellation)}\
            --n_cpus {args.n_cpus}  --mem_gb  {args.mem_gb} --seeds {args.seeds}\
            --diffusion_model {args.diffusion_model} --mod {args.mod}\
            --filtering_type {args.filtering_type}\
            /input /output"
        run(cmd)

    # Upload to s3
    if args.push_location:
        print(f"Pushing to s3 at {args.push_location}.")
        s3_upload(
            args.push_location,
            "/output",
            subject=args.participant_label,
            session="1",
            access_key_id=args.s3_key[0],
            secret_access_key=args.s3_key[1],
        )


if __name__ == "__main__":
    main()
