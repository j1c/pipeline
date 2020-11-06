import subprocess
import shutil
from argparse import ArgumentParser
from pathlib import Path

from hcp2bids import convert, get_data


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
    # arser.add_argument(
    #     "input_dir",
    #     help="""The directory with the input dataset
    #     formatted according to the BIDS standard.""",
    # )
    # parser.add_argument(
    #     "output_dir",
    #     help="""The local directory where the output
    #     files should be stored.""",
    # )
    parser.add_argument("--skip_dmriprep", action="store_true")
    parser.add_argument("--skip_download", action="store_true")
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
        "--session_label",
        help="""The label(s) of the
        session that should be analyzed. The label
        corresponds to ses-<participant_label> from the BIDS
        spec (so it does not include "ses-"). If this
        parameter is not provided all sessions should be
        analyzed. Multiple sessions can be specified
        with a space separated list.""",
        nargs="+",
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
        "--aws_key",
        action="store",
        help="AWS key for HCP S3 bucket.",
    )
    parser.add_argument(
        "--aws_secret_key",
        action="store",
        help="AWS secret key for HCP S3 bucket.",
    )
    args = parser.parse_args()

    if not args.skip_download:
        # Get the data and convert to bids
        print("Downloading data...\n")
        get_data(
            output_path="/input",
            subjects=args.participant_label,
            access_key_id=args.aws_key,
            secret_access_key=args.aws_secret_key,
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
    cmd = f"m2g_bids --participant_label {args.participant_label} --session_label 1\
        --pipeline dwi --skipeddy --voxelsize 1mm\
        --n_cpus {args.n_cpus}  --mem_gb  {args.mem_gb} --seeds {args.seeds}\
        --diffusion_model {args.diffusion_model} --mod {args.mod}\
        --filtering_type {args.filtering_type} --parcellation {args.parcellation}\
        /input /output"
    run(cmd)


if __name__ == "__main__":
    main()
