"""CleanHour: carbon- and price-aware scheduling for AI jobs on India's grid."""
import os

# Some Windows numpy/scipy builds crash on import with many BLAS threads.
for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

__version__ = "0.1.0"
