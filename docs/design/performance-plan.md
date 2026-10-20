# Performance methodology

Run `python -m gramflux.tools.benchmark --iterations 5000 --rounds 5` on an otherwise
idle machine. JSON records Python/platform/processor, dependency versions, exact input
shape/size, each round, median and a separately sampled tracemalloc peak. Warm-up and
GC happen before timings. A correctness check compares bytes before measurement.

The current benchmark uses one identical 64-byte inputFile constructor for GramFlux's
independent codec and Telethon's generated codec. Both return normal objects; neither
performs network I/O. Bounds checking and type validation differ, so these timings
compare implemented behavior, not interchangeable security guarantees. Tracemalloc
peaks measure traced transient allocations over a short loop, not RSS per session or
retained heap. Results on a shared virtual machine are noisy.

`research/benchmark.json` is a measured baseline, not a hard-coded competitor table.
The independent codec is slower on this input. No optimization has been justified yet.
Profile representative nested messages/vectors and flags before specializing encoding.
Cache descriptors only if profiles show lookup cost, while preserving schema/version
validation and bounds. Do not add native extensions before measuring their benefit.

Not measured yet: RPC latency/throughput, multiple-session RSS, dispatch overhead,
SQLite latency, sustained file throughput/peak RSS, reconnect recovery or Telegram
server behavior. A fair future network comparison must use the same DC/account
permissions, operation payload, machine, transport, retries, concurrency and conditions,
record distributions and avoid load that violates Telegram terms. Controlled server
fault-injection results must be separated from actual Telegram tests. File benchmarks
must stream from disk at fixed part sizes and measure memory separately from latency.
