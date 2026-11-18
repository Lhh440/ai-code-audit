# TypeScript specifics

Language-shaped versions of the general failure modes. Read before the sweep.

## API surface that models invent most often

Check each against the installed `.d.ts`, not against memory.

- `fetch`: no `signal`, `res.json<T>()` as if it validates, `res.ok` unchecked
- `Array`: `.toSorted`/`.findLast` assumed on old targets, `.at(-1)` on `lib: es5`
- `Promise`: `Promise.any` without a rejection handler, `.then` with two functions and no `catch`
- `zod`/`yup`: `.parse` where `.safeParse` was needed, schema drift from the type
- `react`: `useEffect` deps omitted, `useCallback` on a function that closes over state, `key={index}`
- `express`: `next(err)` forgotten in an async handler, `req.body` trusted before validation
- `node:crypto`: `createHash` used for passwords, `randomBytes` vs `randomUUID` mixed up
- `tsconfig`: `strict` off in a file-scoped way, `skipLibCheck` used to silence a real error

## Cheap correctness probes

```bash
node_modules/.bin/tsc --noEmit --pretty false    # the real oracle; run it
node_modules/.bin/eslint --no-fix <file>         # needs eslint installed
node --input-type=module -e "await import('./x.js')"   # module graph resolves
```

`tsc` is the highest-value probe in the whole skill. If the project has a
`tsconfig.json` and a local `tsc`, a type error is a fact, not an opinion — and
`// @ts-ignore` in the diff is how a fact gets hidden.

## TypeScript-specific tells

| tell | consequence |
|---|---|
| `as any`, `<any>` | the mismatch it hides stays |
| `@ts-ignore` | silent even after the error is fixed |
| `@ts-expect-error` with no message | same, plus nobody knows why |
| `!` on `process.env.X` | `undefined` at runtime, typed as present |
| `catch {}` | failure indistinguishable from success |
| `res.json()` without `res.ok` | 500 pages parse as data |
| `fetch` without `signal` | no timeout, hang until the socket dies |
| `innerHTML` on API data | XSS |
| `JSON.parse` unguarded | throws on an empty 204 body |
| `.sort()` | numbers sorted as strings |
| `key={index}` | reordered lists reuse the wrong state |
| `useEffect(fn)` with no deps array | runs every render |

## Module and config smells

- an import added but not to `package.json` (works locally, dies in CI)
- `paths` alias used in one direction only, `moduleResolution` relaxed to match
- `"strict": false` or `skipLibCheck` turned on inside an unrelated diff
- `.d.ts` hand-edited to match broken code rather than the other way round
- `export *` added, which makes every symbol check in this skill go quiet
- `eslint-disable-next-line` without a rule name
