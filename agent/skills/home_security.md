# home_security

## Known Persons
- edu
- person_b
- person_c

## Thresholds
confidence_min: 0.80
night_start: 22
night_end: 6

## Alert Rules

| Condition                          | Action                        | Priority  |
|------------------------------------|-------------------------------|-----------|
| known person, any time             | log only                      | INFO      |
| unknown person, daytime            | telegram alert + snapshot     | WARNING   |
| unknown person, night window       | telegram alert + snapshot     | CRITICAL  |
| confidence < threshold             | treat as unknown              | —         |
| parse error / inference failure    | log error, no alert           | ERROR     |

## Snapshot
Save JPEG to $SNAPSHOT_DIR/{timestamp}_{priority}.jpg on WARNING or CRITICAL.
