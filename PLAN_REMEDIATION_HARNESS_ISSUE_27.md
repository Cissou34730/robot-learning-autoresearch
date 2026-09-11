# Plan de remédiation du harnais — Issue 27

Branche : `harness/issue-27-remediation`.

Ce document est le plan de travail (en français). **Tout le contenu produit dans
le dépôt — code, commentaires, documentation, messages de commit, tests — reste
en anglais.**

---

## 1. Contexte

La campagne v4 en cours (`e9b968c4-…`) montre à la fois un progrès réel et une
régression par rapport à la campagne précédente : le Researcher répète des
interventions sur le même « gap » mesuré, mesure peu, conclut de façon binaire,
et se heurte à des frictions de contrat (chemins d'évidence `best_known`, double
empreinte de comparaison, bruit du brief).

L'issue 27 propose dix étapes correctives. Son diagnostic a été vérifié fichier
par fichier avant d'écrire ce plan. La section 2 note ce qui est confirmé, ce qui
est incomplet, et les deux écarts assumés.

Principe directeur repris de l'issue : **retirer de la complexité et corriger des
biais, ne pas ajouter de contrôles Runner.**

---

## 2. Revue critique de l'issue 27

### 2.1 Points confirmés par lecture du code

| Étape | Vérification |
| --- | --- |
| 1 | `research/program.md` impose bien l'ancrage `best_known` ; `run_research.ps1` le répète dans les trois prompts (post-training, lineage decision, new hypothesis). |
| 2 | `program.md` contient bien « request only measurements… », « Minimize redundant… », « Prefer the simplest evidence sufficient… » ; les prompts `post-training analysis` et `evaluation design` répliquent la minimisation. |
| 4 | Les prompts demandent une comparaison binaire « expected vs contradicting ». |
| 5 | `program.md` § *Experiment preparation* impose bien « Only after choosing the mechanism and intervention, choose continuation, replication, or training ». |
| 6 | Le brief affiche 24 lignes de checkpoints, dont 22 `unmeasured`. |
| 7 | `comparison_semantics` est bien une seconde empreinte empilée sur `evaluation_semantics`. |
| 8 | `TRAINING_TARGET_RADIUS_RANGE` et `make_training_env()` vivent dans `robot_learning/scenario/environment.py`, donc dans l'empreinte d'évaluation. |
| 9 | Le contrat `best_known` exige bien un tableau `evidence` de chemins recopiés à la main. |

### 2.2 Compléments manquants dans l'issue (à traiter quand même)

1. **Ancrage `best_known` : deux emplacements dans `program.md`, pas un.**
   L'issue ne cite que le § *Scientific memory and direction*. Le § *Post-training
   analysis* contient la même contrainte (« Establish a concrete next direction
   anchored to … the unresolved measured behavior of `best_known` »). Les deux
   doivent être corrigés, sinon la contrainte survit.

2. **Étape 3 déjà à moitié présente.** `program.md` § *Post-training analysis*
   dit déjà « If a proposed mechanism depends on an unmeasured quantity
   observable on saved policies, measure it before launching a
   mechanism-specific intervention. » Le vrai manque est **dans le prompt**
   `run_research.ps1`. L'étape 3 est donc surtout un travail de prompt + la règle
   « un seul mécanisme causal manipulé » à ajouter dans `program.md`.

3. **Étape 4 : ne pas créer un second vocabulaire.** `research/instruments.md`
   impose déjà pour `Hypothesis assessment` le vocabulaire
   *supported / partly supported / contradicted / unresolved*. L'issue en propose
   un autre (*supported / partially supported / weakened / contradicted /
   inconclusive*). **Un seul vocabulaire doit exister.** On retient celui de
   l'issue et on aligne `instruments.md` dessus.

4. **Étape 5 : le prompt `new hypothesis` porte le même ordre inversé** que
   `program.md`. L'issue ne le mentionne pas. À corriger avec l'étape 5.

5. **Étape 6 : le brief contient deux blocs de checkpoints, pas un.**
   Outre le tableau « Latest experiment » (`_render_v4_research_brief`), la
   section « Current experiment checkpoints available for measurement »
   (`_current_lineages_and_recipes_lines`, ~ligne 479) réémet les 24 mêmes
   checkpoints avec leur chemin d'artefact. Compacter le premier sans le second
   ne retire que la moitié du bruit. **Contrainte forte :** les identifiants de
   modèle (`checkpoint-<steps>`) doivent rester énumérés quelque part, car ils
   sont la valeur attendue du champ `candidate` d'une requête de mesure.

6. **Étape 8 : trois consommateurs, pas un.** `robot_learning/train.py`,
   `research/benchmark_envs.py`, `tests/training/test_active_learning_method.py`,
   `tests/scenario/test_environment.py`, `tests/autoresearch/test_policy_runtime.py`.
   De plus, `tests/autoresearch/test_scenario_boundary.py` (~l.176, ~l.374) et
   `tests/benchmark/test_task_reference_panel.py` (~l.247) contiennent des
   assertions littérales sur `make_training_env` : elles doivent être relues, pas
   seulement « adaptées mécaniquement ».

### 2.3 Écarts assumés par rapport à l'issue

#### Écart A — Étape 7 : supprimer `comparison_semantics` **et** corriger la portée de `evaluation_semantics`

*Constat.* `evaluation_semantics` hache l'arborescence `robot_learning/scenario/`
(hors fichiers protégés, hors `PRESENTATION_ONLY_PATHS`, hors
`MODEL_CONTAINED_RUNTIME_PATHS`) plus `policy_runtime.py` et `evaluate.py`. Elle
inclut donc `robot_learning/scenario/reward.py`.

*Problème.* Le reward est l'intervention la plus fréquente du Researcher, et il
n'influence **pas** le succès d'une policy sauvegardée : dans
`environment.py::step`, `is_success = terminated = held_steps >= hold_steps_required`,
calculé indépendamment de `reach_reward`. La comparaison, elle, ne consomme que
les identités `(episode, episode_seed, success)`
(`_validated_historical_panel_records`). Supprimer `comparison_semantics` sans
rien d'autre invaliderait donc toute réutilisation de mesure historique dès qu'un
reward est modifié — c'est-à-dire presque à chaque expérience. Ce serait
réintroduire par la bande la friction que `comparison_semantics` avait été créé
pour éviter (les expériences 4 et 5 ont réutilisé la mesure de l'expérience 1
grâce à lui).

*Décision.* On applique l'étape 7 telle que demandée (une seule empreinte,
`evaluation_semantics`), **et** on étend le principe de l'étape 8 : le reward
sort de l'identité de mesure, exactement comme la distribution d'entraînement.
Concrètement, on ajoute un ensemble nommé d'exclusions « training-only »
contenant `robot_learning/scenario/reward.py` et le nouveau
`robot_learning/scenario/training_environment.py`.

*Garde-fou.* Le mécanisme d'inclusion par défaut (`rglob` sur `scenario/`) est
conservé : tout nouveau fichier de scénario compte automatiquement dans
l'identité de mesure. Seuls les fichiers explicitement nommés sortent. Un test
documente que le succès et la terminaison ne doivent pas dépendre d'un fichier
exclu.

#### Écart B — Étape 9 : la comparabilité incombe au Researcher, pas au Runner

L'issue demande que le Runner n'exige plus qu'« au moins une mesure » pour un
nouveau `best_known`. Cela supprime de fait la vérification actuelle de
compatibilité instrument/panel entre challenger et incumbent
(`_evidence_records_compatible` appelé depuis la branche `best_known`). C'est
cohérent avec « le Runner ne décide de rien scientifiquement », mais il faut
l'assumer explicitement : **la comparabilité devient une responsabilité du
Researcher**, documentée dans `program.md`. Le Runner conserve uniquement
l'identité de modèle et l'intégrité de fichier.

#### Écart C — Étape 2 : pas de règle « panel indépendant sous 98 % » à retirer

L'issue demande de « ne pas imposer de panel indépendant sous 98 % ». Aucune
règle de ce type n'existe dans `program.md`, `instruments.md` ou
`run_research.ps1` : le seuil de 98 % apparaît uniquement dans du texte
**rédigé par le Researcher** dans `research/postmortems.md`. Aucun changement de
harnais n'est requis. On se contente de ne pas réintroduire une telle règle.

---

## 3. Invariants non négociables

À préserver dans tous les lots :

- `working` distinct de `best_known` ;
- identité exacte du modèle mesuré (`model_fingerprint`) ;
- détection d'un artefact de mesure modifié après création
  (`evaluation_artifact_fingerprint`) ;
- provenance Git de la recette scientifique ;
- évaluations facultatives et motivées ;
- plusieurs tours de mesure pendant l'analyse post-training ;
- séparation « Researcher décide / Runner exécute ».

Interdits :

- nouvelle phase, nouveau fichier de contrôle, nouvelle machine à états ;
- nouveau champ JSON dans `proposal.json` ou `evaluation_request.json` ;
- contrôle Runner sur le nombre de fichiers modifiés ;
- backfill ou migration des JSON historiques ;
- exécution d'un entraînement, d'une campagne, du benchmark final ou de la suite
  de tests complète dans ce chantier.

---

## 4. Lots de travail

Chaque lot = une sous-session + un commit. Les messages de commit reprennent le
découpage de l'issue.

### L1 — `fix: restore scientific direction and evaluation freedom`

Couvre les étapes 1 et 2.

**`research/program.md`**

- § *Scientific memory and direction* : remplacer l'obligation
  « Direction must name its highest-priority unresolved behavioral gap » par :
  - `Direction` nomme la question scientifique temporaire qui sert le mieux
    l'objectif de campagne ;
  - `working`, `best_known`, les candidats et leurs comportements sont des
    preuves disponibles, aucun ne fixe la direction ;
  - une direction peut approfondir, prendre du recul ou changer de niveau
    d'explication ;
  - une prochaine direction reste requise tant que la campagne continue, mais
    elle est révisable.
- § *Post-training analysis* : même correction sur
  « Establish a concrete next direction anchored to … `best_known` ».
- § *Evidence obligation* : retirer « request only measurements… »,
  « Minimize redundant or decision-irrelevant evidence… », « Prefer the simplest
  evidence sufficient… ». Les remplacer par : l'étendue des mesures suit
  l'incertitude scientifique ; éviter les mesures réellement redondantes ;
  plusieurs checkpoints, panels ou tours sont légitimes s'ils peuvent révéler une
  dynamique, une dépendance au panel ou un mécanisme mal identifié ; aucune
  comparaison, réplication ou mesure `task_reference` n'est obligatoire ni
  préférée.
- Conserver telles quelles : la primauté du comportement mesuré sur un proxy
  d'entraînement, et l'interdiction de laisser une statistique d'entraînement
  devenir automatiquement la direction principale.

**`run_research.ps1`**

- Supprimer les trois ancrages `best_known` (prompts post-training analysis,
  lineage decision, new hypothesis).
- Prompt `new hypothesis` : commencer par *campaign objective → current
  scientific strategy → available evidence*.
- Prompts `post-training analysis` et `evaluation design` : retirer toute
  incitation au plus petit ensemble de mesures ; conserver l'obligation
  d'énoncer la question scientifique ; dire explicitement que la portée peut être
  élargie si cela aide à comprendre le résultat ou à choisir la suite ; conserver
  la possibilité de clore sans nouvelle mesure.

**`research/instruments.md`**

- Uniquement la description opérationnelle : aucune préférence scientifique entre
  instruments ; conserver la limite technique de trois modèles distincts par
  requête (elle n'empêche ni plusieurs panels ni plusieurs tours) ; retirer toute
  formulation qui présente une mesure comme préférable à une autre.

**Tests** — adapter uniquement les assertions concernées :
`tests/autoresearch/test_research_protocol.py`,
`tests/autoresearch/test_researcher_session.py`,
`tests/autoresearch/test_scientific_reasoning.py`.
Ajouter les assertions : les prompts n'imposent ni `best_known`, ni panel, ni
quantité minimale de mesure.

---

### L2 — `fix: support diagnostic-first and non-binary reasoning`

Couvre les étapes 3 et 4.

**`research/program.md`**

- Rendre explicite (sans nouvelle phase) : quand la prochaine hypothèse dépend
  d'un comportement non encore observé sur une policy sauvegardée, chercher
  d'abord cette information (inspection, logs, instrumentation, ou un tour de
  mesure supplémentaire) ; ne pas lancer un entraînement seulement pour
  découvrir si le mécanisme supposé existe.
- Ajouter : une intervention manipule **un seul mécanisme causal identifiable** ;
  plusieurs fichiers sont autorisés lorsqu'ils implémentent ensemble cette même
  manipulation. Aucun contrôle Runner sur le nombre de fichiers.
- Vocabulaire d'observation explicite et **unique** : `supported`,
  `partially supported`, `weakened`, `contradicted`, `inconclusive`. Demander de
  préserver les changements directionnels significatifs même lorsque le taux de
  réussite ne bouge pas.
- Conserver `expected_observation`, `contradicting_observation` et la distinction
  « intervention précise » / « mécanisme général ».

**`research/instruments.md`**

- Aligner le libellé de `Hypothesis assessment` sur ce vocabulaire unique
  (remplacer « supported, partly supported, contradicted, or unresolved »).
  Aucun nouveau champ.

**`run_research.ps1`**

- Prompt post-training, avant le choix entre mesure et clôture, ajouter :

  ```text
  If the next proposed intervention depends on an unmeasured behavior of a saved
  policy, obtain that evidence during the current analysis phase before closing.
  ```

- Remplacer « compare the result with expected and contradicting observations »
  par une formulation demandant : où le résultat se situe entre les deux
  prédictions ; quels signaux partiels ou inattendus ont été observés ; ce que
  l'intervention exacte établit ; ce qui reste inconnu sur le mécanisme.

**Tests** — `tests/autoresearch/test_post_training_analysis.py`,
`tests/autoresearch/test_scientific_reasoning.py`,
`tests/autoresearch/test_researcher_session.py` : les résultats partiels sont
explicitement permis ; le prompt demande la preuve diagnostique avant
intervention.

---

### L3 — `fix: clarify continuation and replication reasoning`

Couvre l'étape 5.

**`research/program.md`** — § *Experiment preparation*, nouvel ordre :

1. choisir la question scientifique ;
2. choisir l'opération adaptée ;
3. si intervention : définir le mécanisme et la manipulation ;
4. si `continuation` : formuler une hypothèse sur la trajectoire d'apprentissage
   ou le budget ;
5. si `replication` : formuler une hypothèse sur la variabilité du processus ;
6. justifier ensuite le parent et l'initialisation.

**`run_research.ps1`** — prompt `new hypothesis` : refléter le même ordre
(supprimer « Only after choosing the mechanism and intervention… »).

**`research/instruments.md`** — sans changer le schéma, préciser le sens des
`kind` existants : `continuation` = prédiction sur la poursuite, le plateau ou la
dégradation ; `replication` = prédiction sur la reproductibilité ou la variance ;
`training` = prédiction causale sur l'intervention. Aucune opération recommandée
par défaut.

**Tests** — `tests/autoresearch/test_research_protocol.py`,
`tests/autoresearch/test_researcher_session.py` (assertions d'ordre / de prompt
uniquement).

---

### L4 — `refactor: compact training proxy presentation`

Couvre l'étape 6, étendu au second bloc de checkpoints (§ 2.2 point 5).

**`research/build_research_brief.py`**

- `_render_v4_research_brief()` : afficher individuellement **tous les
  checkpoints mesurés** ; ne plus émettre une ligne de tableau complète par
  checkpoint non mesuré ; ajouter une ligne compacte donnant le nombre de
  checkpoints non mesurés, la plage de steps disponible, et le renvoi aux logs
  détaillés.
- Ajouter un résumé compact de trajectoire d'entraînement : valeur initiale ;
  meilleur proxy observé et son step ; valeur finale. Toujours qualifié de
  `training proxy`.
- `_current_lineages_and_recipes_lines()` : compacter de la même façon la section
  « Current experiment checkpoints available for measurement ». **Tous les
  identifiants `checkpoint-<steps>` restent énumérés** (ils sont la valeur
  attendue de `candidate`) ; ce sont les lignes par checkpoint et les chemins
  d'artefact des checkpoints non mesurés qui sont condensés. Le chemin de base
  des artefacts de l'expérience reste indiqué une fois.
- Aucune donnée n'est supprimée du state ; seule la présentation change.

**Tests** — `tests/autoresearch/test_research_context.py`,
`tests/autoresearch/test_console_presentation.py` : un entraînement à 24
checkpoints ne produit plus 24 lignes ; les checkpoints mesurés restent
visibles ; tous les identifiants restent présents dans le brief.

---

### L5 — `refactor: use one evaluation compatibility identity`

Couvre l'étape 7 + écart A. **Lot le plus risqué : à faire seul, après L4.**

**`research/runner_protocol.py`**

- Supprimer `COMPARISON_SEMANTICS_PATHS`, `COMPARISON_SEMANTICS_VERSION_PATH`,
  `comparison_semantics_fingerprint()`, la lecture de
  `PRIMARY_COMPARISON_SEMANTICS_VERSION`, et la compatibilité spéciale fondée sur
  `comparison_semantics` dans `_evidence_records_compatible()`,
  `_compatible_primary_panels()`, `_development_evidence_catalog()` et
  `_resolved_paired_evidence_plan()`.
- Compatibilité résultante d'une comparaison : **même instrument** + **mêmes
  paramètres de panel** (seed, épisodes, panel éventuel) + **même
  `evaluation_semantics`** + mêmes identités d'épisodes.
- Conserver `model_fingerprint`, `evaluation_artifact_fingerprint`, et le rejet
  d'un fichier de résultat modifié après mesure.
- Écart A : ajouter un ensemble nommé (p. ex. `TRAINING_ONLY_PATHS`) exclu de
  `evaluation_semantics_paths()`, contenant `robot_learning/scenario/reward.py`
  et `robot_learning/scenario/training_environment.py` (créé en L6). Documenter
  en une ligne pourquoi : ces fichiers ne déterminent ni le rejeu d'une policy
  sauvegardée ni son succès. Conserver l'inclusion par défaut de tout autre
  fichier de `scenario/`.

**`research/run_experiment.py`, `research/runner_execution.py`,
`research/runner_console.py`**

- Ne plus produire ni propager `comparison_semantics`,
  `candidate_evaluation_semantics`, `reference_evaluation_semantics`. Produire
  uniquement `evaluation_semantics`.

**`research/instruments.md`**

- Réécrire le paragraphe de compatibilité des mesures historiques : un seul
  contrat, plus de « primary comparison semantics ».

**Historique** — les anciens champs restent lisibles et sont ignorés ; aucun
backfill ; une mesure sans `evaluation_semantics` n'est simplement pas
réutilisable et peut être remesurée.

**Tests** — `tests/autoresearch/test_execution_contract.py`,
`tests/autoresearch/test_lineage_roles.py`,
`tests/autoresearch/test_research_protocol.py` : les comparaisons utilisent un
seul contrat de compatibilité ; une mesure modifiée reste rejetée ; une identité
de modèle erronée reste rejetée.

---

### L6 — `refactor: isolate training-only environment setup`

Couvre l'étape 8. **Après L5** (L5 nomme déjà le nouveau fichier dans les
exclusions).

**`robot_learning/scenario/environment.py`** — conserver l'environnement
partagé, la mécanique réellement utilisée par l'évaluation et
`make_evaluation_env()`. Retirer `TRAINING_TARGET_RADIUS_RANGE`,
`make_training_env()` et toute logique exclusivement destinée à modifier la
distribution d'entraînement. Mettre à jour le docstring du module (il annonce
aujourd'hui `make_training_env()`).

**Nouveau `robot_learning/scenario/training_environment.py`** — uniquement les
paramètres et comportements spécifiques au training, une éventuelle sous-classe
pour les variations de sampling/curriculum, et `make_training_env()`. Aucune
abstraction, registry ou système de plugins.

**Appels à mettre à jour** — `robot_learning/train.py`,
`research/benchmark_envs.py`, `tests/training/test_active_learning_method.py`,
`tests/scenario/test_environment.py`, `tests/autoresearch/test_policy_runtime.py`.

**Assertions littérales à relire** (ne pas renommer mécaniquement) —
`tests/autoresearch/test_scenario_boundary.py` (~l.176 surface requise, ~l.374
`make_training_env` absent de `normalization.py`) et
`tests/benchmark/test_task_reference_panel.py` (~l.247).

**Tests** — ajouter : un changement training-only (nouveau fichier ou
`reward.py`) **ne change pas** `evaluation_semantics` ; un changement réel de
l'évaluateur ou de la mécanique partagée **le change**.

---

### L7 — `fix: resolve best-known evidence internally`

Couvre l'étape 9 + écart B.

**`research/instruments.md`** — nouveau contrat de clôture :

```json
"best_known": {
  "candidate": "<available model identifier>",
  "reason": "<scientific reason>"
}
```

Supprimer le tableau `evidence`. Règles : champ absent → `best_known` conservé ;
même modèle explicitement sélectionné → opération idempotente ; autre modèle →
le Runner retrouve automatiquement les mesures enregistrées pour ce modèle ; un
nouveau `best_known` doit posséder au moins une mesure, mais le Runner ne juge
pas si elle est scientifiquement suffisante.

**`research/runner_protocol.py`** — lors du remplacement : résoudre le modèle par
son identifiant ; récupérer ses mesures dans l'état courant ; vérifier identité
de modèle et intégrité des fichiers ; enregistrer ces preuves dans la lignée ;
ne plus demander de chemins au Researcher. Retirer la validation de
comparabilité challenger/incumbent (écart B). Le Runner ne compare pas les scores.

**Messages d'erreur** — citer le modèle demandé, les identifiants de modèles
disponibles, et l'absence éventuelle de mesure. Ne plus demander de corriger un
chemin d'artefact à la main.

**`run_research.ps1`** — prompt de clôture, ajouter :

```text
If best_known remains unchanged, omit the best_known field.
Do not restate or reselect it.
```

**`research/program.md`** — écart B : indiquer que la comparabilité des preuves
soutenant une désignation `best_known` est une responsabilité du Researcher, le
Runner ne vérifiant que l'identité de modèle et l'intégrité des fichiers.

**Tests** — `tests/autoresearch/test_lineage_roles.py` (principal),
`tests/autoresearch/test_research_protocol.py` : `best_known` absent conserve la
lignée ; sa sélection ne demande plus de chemins manuels ; une mauvaise identité
de modèle reste rejetée ; un fichier de mesure modifié reste rejeté ; un modèle
sans aucune mesure est rejeté avec un message citant les identifiants
disponibles.

---

### L8 — `docs: record targeted harness corrections`

- `research/PROTOCOL_DECISIONS.md` : consigner les raisons des corrections, en
  incluant explicitement les écarts A, B et C.
- `research/program.md` : relecture finale de cohérence (méthode scientifique).
- `research/instruments.md` : relecture finale des contrats opérationnels.
- `AGENTS.md` : mettre à jour uniquement si L5/L6 rendent une phrase fausse
  (p. ex. mention de l'empreinte de comparaison ou de la disposition de
  `scenario/`).
- **Ne pas modifier `research/scenario.md`.**

---

## 5. Ordre d'exécution

```
L1 ──▶ L2 ──▶ L3        (prompts + program.md + instruments.md, séquentiel :
                         même fichier run_research.ps1)
L4                       (indépendant, brief seulement)
L5 ──▶ L6                (empreinte puis isolation training)
L7                       (après L5 : dépend du catalogue d'évidence)
L8                       (dernier)
```

L1→L2→L3 touchent tous `run_research.ps1`, `program.md` et `instruments.md` :
strictement séquentiel. L4 peut être lancé en parallèle de L1. L7 doit venir
après L5 car il réutilise `_development_evidence_catalog`.

---

## 6. Règles imposées aux sous-sessions

1. **Anglais** pour tout ce qui entre dans le dépôt.
2. **Aucun entraînement, aucune campagne, aucun benchmark, aucun test Git
   end-to-end, aucune suite complète.**
3. Validation autorisée, ciblée uniquement :

   ```powershell
   uv run pytest -q tests/autoresearch/test_research_protocol.py
   uv run pytest -q tests/autoresearch/test_researcher_session.py
   uv run pytest -q tests/autoresearch/test_research_context.py
   uv run pytest -q tests/autoresearch/test_lineage_roles.py
   uv run pytest -q tests/autoresearch/test_post_training_analysis.py
   uv run pytest -q tests/autoresearch/test_scientific_reasoning.py
   uv run pytest -q tests/autoresearch/test_console_presentation.py
   uv run pytest -q tests/autoresearch/test_execution_contract.py
   uv run pytest -q tests/scenario tests/training
   uv run ruff check <fichiers modifiés>
   ```

   Chaque lot n'exécute que les suites qu'il touche.
4. **Ne pas toucher** aux artefacts de campagne :
   `research/research_state.json`, `research/results.jsonl`,
   `research/EXPERIMENTS.md`, `research/brief.md`, `research/postmortems.md`,
   `research/evaluations/`, `research/checkpoints/`, `models/`.
   Ils sont déjà modifiés dans l'arbre de travail par la campagne en cours et
   doivent le rester.
5. Ne pas ajouter de champ JSON, de phase, de fichier de contrôle ni de contrôle
   Runner.
6. Ne pas exécuter de commande Git mutante : la session principale commite.
7. Signaler tout écart nécessaire plutôt que de l'appliquer silencieusement.

---

## 7. Critères d'acceptation

- Aucun prompt de `run_research.ps1` n'impose l'ancrage `best_known`, un panel
  particulier, ou une quantité minimale de mesure.
- `program.md` autorise explicitement les verdicts partiels et la démarche
  diagnostic-d'abord, avec un vocabulaire d'observation unique partagé avec
  `instruments.md`.
- L'ordre « question → opération → mécanisme/hypothèse → parent » figure dans
  `program.md` et dans le prompt `new hypothesis`.
- Un entraînement à 24 checkpoints ne produit plus 24 lignes de tableau ni 24
  lignes d'inventaire, tout en conservant les mesures et tous les identifiants
  requêtables.
- `comparison_semantics` n'existe plus dans le code ; une seule identité de
  compatibilité est produite et consommée.
- Un changement de `reward.py` ou du nouveau `training_environment.py` ne change
  pas `evaluation_semantics` ; un changement de `evaluation.py`,
  `environment.py`, `policy_runtime.py` ou `evaluate.py` le change.
- Une clôture peut désigner `best_known` sans citer de chemin d'artefact ;
  omettre le champ conserve la lignée.
- `ruff check` propre sur les fichiers modifiés ; suites ciblées vertes.
