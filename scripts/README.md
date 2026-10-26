# Scripts

## nerve_hash.py

[nerve_hash.py](nerve_hash.py) hashes nerve class names using MurmurHash64A. Matches update [nerves.csv](../data/nerves/nerves.csv).

Pass names directly or read them from a file, one per line:

```sh
python scripts/nerve_hash.py AllDeadWatcherNrvWatch AllDeadWatcherNrvWait
python scripts/nerve_hash.py --file names.txt
```

Search for a target hash using a class name and the ranked nerve name list:

```sh
python scripts/nerve_hash.py --brute FC07A3C06255F155 --class AllDeadWatcher
```

Checks `HostType` first, then the specified class. Without `--class`, checks all actors in `reference/actors/actor_names.txt` after `HostType`. Prints each class as it is checked.

```sh
python scripts/nerve_hash.py --brute FC07A3C06255F155
```

To combine words from multiple lists:

```sh
python scripts/nerve_hash.py --brute 29D231D438558CAC --class Barrier --wordlist scripts/reference/nerve_names/nerve_prefixes.txt scripts/reference/nerve_names/nerve_suffixes.txt
```

## IDA

[ida/ida_rename_nerves.py](ida/ida_rename_nerves.py) renames functions in IDA to match `data/nerves/nerves.csv`.

- `exe` functions try to be named when they exist
- the class name is prepended to HostType nerves (maybe this is too messy)

## Reference

[reference/nerve_names/](reference/nerve_names/): Nerve and action names from SMO and DKB for hash bruteforcing.

[reference/actors/actor_names.txt](reference/actors/actor_names.txt): Actor classes to check when no class is specified.
