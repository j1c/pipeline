import subprocess
import shutil
from argparse import ArgumentParser

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
    parser.add_argument(
        "--nprocs",
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
        nargs="+",
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
    parser.add_argument("--aws_key", action="store")
    parser.add_argument("--aws_secret_key", action="store")
    args = parser.parse_args()

    # Get the data and convert to bids
    get_data(
        output_path="/input",
        subjects=args.participant_label,
        access_key_id=args.aws_key,
        secret_access_key=args.aws_secret_key,
    )
    convert(
        input_path="/input",
        output_path="/input",
        include_ses=True,
    )

    # Run dmriprep
    cmd = f"dmriprep /input /output participant -w /work_dir -s 1 \
        --participant_label {args.participant_label} \
        --nprocs {args.n_cpus} --omp_nthreads {args.n_cpus} --mem_gb {args.mem_gb} "
    run(cmd)

    # Delete work dir
    shutil.rmtree("/work_dir")

    # Rename files

    # Run m2g
    # cmd = f"m2g_bids --participant_label  {args.participant_label} --session_label 1 \
    #     --pipeline dwi --skipeddy --voxelsize 1mm \
    #     --n_cpus {args.n_cpus}  --mem_gb  {args.mem_gb} -seed {args.seeds} \
    #     --diffusion_model {args.diffusion_model} --mod {args.mod}  \
    #     --filtering_type {args.filtering_type} \
    #     /input /output"
    # run(cmd)


if __name__ == "__main__":
    main()