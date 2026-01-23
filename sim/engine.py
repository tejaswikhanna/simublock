import threading

mine_event = threading.Event()
chain_running = False


def start_sim(app, emit, pending_ops, metrics, EXPERIMENT):
    global chain_running

    bc = Blockchain()
    app.blockchain = bc
    metrics["start_time"] = time.time()
    emit("Simulation initialized")

    emit("Blockchain object attached to app")
    emit(f"ENGINE: chain length = {len(bc.chain)}")
    emit(f"Genesis block index: {bc.chain[0].i}")

    while len(bc.chain) < EXPERIMENT["max_blocks"]:

        if not chain_running:
            time.sleep(0.2)
            continue

        mine_event.wait()   # ⬅ waits for the SAME event

        if not pending_ops:
            emit("No operations to mine")
            mine_event.clear()
            continue

        ops = []
        while pending_ops and len(ops) < EXPERIMENT["block_capacity"]:
            ops.append(pending_ops.pop(0))

        emit(f"Mining block with {len(ops)} operations")

        block = Block(len(bc.chain), bc.last().h, ops)
        consensus = get_consensus(EXPERIMENT)
        block = consensus.propose_block(block)

        if consensus.validate_block(block, bc):
            bc.add(block)

        metrics["ops_committed"] += len(ops)
        mine_event.clear()
