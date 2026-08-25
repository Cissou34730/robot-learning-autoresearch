# Experiment log

**Best so far:** 55% (experiment 8: ent_coef 0.01)

## Lessons that shaped the current best (condensed from experiments 0-11)

- Exp 1 (n_steps 256, reverted): more updates alone did not help; noise-driven contact.
- Exp 2 (action cost 0.05): +8 pts. Flailing now pays; policy more directed.
- Exp 3 (SUCCESS_BONUS 25 -> 5): +26 pts. Sparse/dense scale balance stabilized value fitting — binding-constraint fix.
- Exp 4 (hard near-zone gate, reverted): discontinuity at the gate poisoned advantages. Lesson: shaping must be continuous in distance.
- Exp 5 (exponential closeness potential C=2, lambda=0.05): +4 pts, median 3.9 cm. Potential-based shaping works; healthiest training curve so far.
- Exp 6 (C=4): +4 pts, median 3.7 cm. Doubling C converted near-misses without instability.
- Exp 7 (C=8): 53%, reverted. Coefficient scaling exhausted around C=4.
- Exp 8 (ent_coef 0.01): +2 pts to 55%. Current champion; fresh-seed audit confirmed 54% on unseen targets.
- Exp 9 (n_epochs 20, reverted): faster start but mid-run overfit and exploration lock-down; optimization intensity is not the constraint.
- Exp 10 (ent_coef 0.02, reverted): collapsed hard; ent_coef peaked near 0.01.
- Exp 11 (lambda 0.08, reverted): collapsed to 9%. The sharp lambda=0.05 focus near target is load-bearing; do not stretch it outward.

## Remaining untried lever classes

gamma / gae_lambda (credit assignment), net_arch (capacity), PROGRESS_COEFFICIENT scale-up,
ent_coef fine-tune downward (0.005).

Full original notes for experiments 0-11: see `research/archive.md`.

## Results table

| # | Date | Change | Hypothesis | Success % | Mean dist (cm) | Median dist (cm) | Verdict |
|---|------|--------|------------|-----------|----------------|------------------|---------|
