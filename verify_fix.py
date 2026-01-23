
import sys
import os

sys.path.append(os.getcwd())

print("Testing imports...")
try:
    from core.block import Block, Operation
    print("core.block imported")
    from core.blockchain import Blockchain
    print("core.blockchain imported")
    from core.consensus import Consensus, mine
    print("core.consensus imported")
    import sim.engine
    print("sim.engine imported")
    import simublock
    print("simublock imported")
    print("ALL IMPORTS SUCCESSFUL")
except Exception as e:
    print(f"IMPORT ERROR: {e}")
    sys.exit(1)
