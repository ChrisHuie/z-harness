# CEL in Swamp

Expressions are wrapped in `${{ }}` inside YAML string fields. Two places take raw CEL with no
wrapper: a workflow step's `guard` and an `assert` task's `expr`. The `message` of an assert is
interpolated text, so it does use the wrapper.

## Namespaces

| Namespace | Available in | Holds |
|---|---|---|
| `self` | definitions, steps | the current definition: `self.name`, `self.tags.*`, `self.globalArguments.*`; in a forEach step also `self.<item>` and `self._index` |
| `model` | everywhere | other behaviors (legacy name kept): `model.<name>.definition.*`, `.input.*`, `.resource.<spec>.<instance>.attributes.*`, `.file.<spec>.<instance>`, `.execution.status`; `model.method(name, method[, inputs])` runs a method inline |
| `inputs` | definitions and steps | runtime inputs of the behavior run or the workflow run |
| `env` | everywhere | process environment variables |
| `vault` | everywhere | `vault.get(vault, key)`, `vault.put(vault, key, value)` |
| `data` | everywhere | `data.latest(b, n[, vary])`, `data.version(b, n[, vary], v)`, `data.listVersions(b, n)`, `data.findByTag(k, v)`, `data.findBySpec(b, spec)`, `data.query(pred[, select])`; a behavior name may carry a namespace prefix `"ns:behavior"` or `"*:behavior"` |
| `file` | everywhere | `file.contents(behavior, spec)` |
| `run` | step expressions only | `run.id`, `run.workflowId`, `run.workflowName`, `run.startedAt`, `run.tags` |
| `steps` | step expressions only | `steps.<name>.status`, `steps.<name>.outputs.<field>`; resolves when the step runs, never at run start |
| `webhook` | webhook-triggered runs | the delivery payload |

`steps.<name>.outputs` is the flat merge of every JSON resource the step wrote; a later write wins
on a shared attribute name. For a nested workflow step it is keyed by child step name, one level
deep. File outputs and non-JSON resources contribute nothing.

## Idioms

```text
data.latest("checker", "result").attributes.exitCode == 0        guard or assert
data.latest("x", "y").?attributes.?field.orValue("default")        null-safe chain with a default
string(self._index) + "-" + self.file                              index inside a name
size(data.latest("fleet", "nodes").attributes.instances) >= 3
has(inputs.region) && inputs.region in ["us-east-1", "eu-west-1"]
```

`.?` returns null instead of throwing; `.orValue()` supplies the default. Macros `has()`,
`all()`, `exists()`, `exists_one()`, `filter()`, `map()` are available. Timestamp and duration
functions, string methods and type conversions follow standard CEL.

## Evaluated versus inert sources

| Source | Treatment |
|---|---|
| Definition fields, step fields, workflow-level fields | evaluated |
| `swamp workflow run --input` values | inert data, recorded on the run |
| `swamp behavior run --input` values | evaluated, unless `--literal-inputs` |
| Resume `--input` values | inert, deep-merged over the run's inputs, persisted |

Other services' template syntax passes through untouched unless it collides with a Swamp
namespace name, in which case it is reported as an error.

## Data in shell commands

A data value placed into a `command/shell` command arrives as an environment variable named
`__SWAMP_IN_N`; a secret arrives as `__SWAMP_VAULT_N`. Quote them as environment values in the
script rather than splicing their text into the command line. Placements that would split a
value or run it as code are refused.

## Data query fields

`swamp data query '<predicate>' [--select <expr>] [--single] [--limit n]` and `data.query()` share
one record shape. Fields: `id`, `name`, `version`, `isLatest`, `createdAt`, `attributes` (parsed
JSON of a resource), `content` (raw text), `contentType`, `tags`, `modelName` (`behaviorName`
is a synonym), `modelType`, `modelId`, `specName`, `dataType` (`resource`, `file`, `report`),
`lifetime`, `garbageCollection`, `ownerType` (`model-method`, `workflow-step`, `manual`),
`ownerRef`, `source`, `streaming`, `size`, `workflowName`, `workflowRunId`, `jobName`,
`stepName`, `ns`. Functions: `behavior("<name or id>")`, `model("<name or id>")`,
`latestRun("<workflow>")`. `attributes` and `content` load lazily, only when referenced.

```bash
swamp data query 'behavior("lookup") && name == "vendor-755" && isLatest' --select attributes --single
swamp data query 'isLatest && specName == "result" && attributes.exitCode != 0'
swamp data query 'workflowRunId == latestRun("nightly")' --limit 20
```

## Secrets in expressions

A secret may be passed to a method input, concatenated with text, or compared to `null`.
Equality against another value, `size`, conversions, string methods, map keys and
container-to-text interpolation fail with `secret_operation_unsupported`. Routing fields,
placement, paths, `workingDir`, environment keys, and guard or assert results refuse a secret
with `secret_destination_refused`. Call `vault.get` directly; aliases are not supported.
