# Go specifics

Language-shaped versions of the general failure modes. Read before the sweep.

## The oracle

`go vet ./...` and `go build ./...` are facts. Run them (via
`scripts/static_gate_go.sh`) before any reasoning, then ask what the compiler
cannot see: error paths, goroutine lifetimes, timeouts, `defer` placement.
`gofmt -l` output means the diff was never run through a formatter — a strong
"not executed, just generated" tell.

## API surface that models invent most often

- `sql`: `Rows.Close` forgotten, `db.Query` where `QueryRow` was meant, `Scan` arity
- `context`: `Background` inside a request path, `ctx` not passed to `http.NewRequestWithContext`
- `sync`: `WaitGroup.Add` after `go`, `Mutex` without `defer Unlock`, `map` shared across goroutines
- `errors`: `%v` instead of `%w`, `==` on a sentinel, `errors.Is` not used
- `net/http`: `http.Get` (DefaultClient, no timeout) instead of a configured `Client`
- `time`: `time.Now().Sub(x)` instead of `time.Since`, `time.Sleep` in a retry with no backoff
- `slices`/`maps`: `sort.Slice` where `slices.SortFunc` exists on the target version
- `strconv`: `Atoi` error ignored

## Go-specific tells

| tell | consequence |
|---|---|
| `_ = err` / `response, _ :=` | failure becomes silence |
| `if err != nil { }` | error checked, then dropped |
| `if err != nil { return nil }` | the caller sees success |
| `log.Fatal` in a library | `os.Exit` skips every deferred close |
| `defer` inside a `for` | runs at function exit; file handles pile up |
| `panic(true)` in library code | caller must recover without a contract |
| `context.Background()` | cancellation from the caller is lost |
| `http.Get` | no timeout, no reuse |
| `fmt.Sprintf` into `.Exec` | values interpolated, not bound |
| `interface{}` / `any` parameter | untyped seam, no compile help |
| `time.Sleep` in logic | untestable without a clock seam |
| `os.Chdir` | process-global, test-order dependent |

## Cheap probes beyond the gate

```bash
go vet ./...
gofmt -l .
go list -deps ./... | grep -c .     # graph size, unexpected growth
go test -run XXX -count=1 ./...     # compile-only pass
```

## Module smells

- import added but absent from `go.mod` (`go mod tidy` never run)
- `go` directive bumped inside an unrelated diff
- `//nolint` without a linter name
- a new `vendor/` entry without a `vendor/modules.txt` update
- `init()` doing work: import-order side effects
