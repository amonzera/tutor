import sys

if sys.version_info < (3, 10):
    sys.stderr.write("O tutor precisa do Python 3.10 ou mais novo.\n")
    sys.exit(127)

from tutor.cli import main  # noqa: E402

sys.exit(main())
