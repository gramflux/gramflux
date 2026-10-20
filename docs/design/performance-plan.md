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

`research/benchmark.json` is the initial measured baseline;
`research/benchmark-0.2.0a1.json` is the versioned repeat. Each is a measurement, not a hard-coded competitor table.
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


## Controlled transfer pipeline benchmark

`python -m gramflux.tools.transfer_benchmark --size-mib 4 --part-size 65536
--concurrency 1 4 --latency-ms 2 --rounds 3` benchmarks the upload pipeline against a
local async request double. Put this command on one shell line. The source is written
to a temporary disk file in bounded blocks before timing. Warm-up checks accepted-byte
accounting/part counts and, for small files, the source-order checksum. Results contain
Python/platform/dependency versions, timings by round, observed in-flight maximum and
a separate tracemalloc sample, excluding memory instrumentation from timed rounds.

`research/transfers-0.2.0a2.json` records actual results. Simulated sleep latency is an
input, not a Telegram latency measurement. This measures concurrency overlap in the
local pipeline and file I/O, not Telegram bandwidth, independent-network throughput,
backend buffering or RSS. Do not compare these figures with competitor server tests.


## Native engine baseline (0.3)

The former Telethon comparison files are historical measurements, not current runtime
dependencies. The current codec/transfer tools execute only GramFlux. The native engine
uses OpenSSL AES/DH primitives with Python IGE/protocol glue. A 512-KiB IGE baseline
identified byte-by-byte XOR overhead; integer-backed XOR reduced the recorded median
from 0.259218 to 0.099853 seconds on the same input. Every known-answer and envelope
boundary test still passes. See research/native-ige-profile.json. These samples are
local shared-host observations, not a Telegram speed comparison or constant-time audit.
The Python IGE loop is still a material throughput limitation. Profile realistic packet,
request and update workloads before choosing any optional compiled acceleration.


Reproduce the IGE comparison without editing runtime globals:

```bash
python -m gramflux.tools.native_benchmark --size 524288 --rounds 5
```

This tool retains GramFlux's own original bytewise IGE loop solely as a baseline,
checks both implementations produce identical output and decrypt correctly, and records
Python/platform/provider versions plus every round. The new measurement is retained in
research/native-ige-benchmark-0.3.0a1.json; earlier exploratory samples remain historical.

Native event metadata scaling can be reproduced with `python -m gramflux.tools.update_benchmark`. It compares our previous full-cache snapshot with current native emission at 64/1,024/4,096 cached entities, recording five timing rounds and separate tracemalloc peaks. The smaller metadata snapshot trades additional field inspection for bounded per-event retention; the recorded small-cache case is slower. This is not a network or public-handler benchmark.
