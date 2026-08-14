# System Startup and Testing Instructions

This document describes how to prepare, run, test, train, visualize, and deploy the stock exchange system in two modes:

- **Basic mode** — without bot detection mechanisms.
- **Predictive mode with GUARD** — with the Guard module, Redis, and an XGBoost model.

> **General requirements**
>
> - Use **ZSH** or **SH** scripts.
> - Load tests should run for at least **5 minutes (300 seconds)**.
> - Test names should consistently encode the duration, number of users, and traffic profile where applicable.

---

## 1. System Preparation

### 1.1. Clone the repository

```bash
git clone ...
```

### 1.2. Install Node.js dependencies

Run the dependency installation command in the appropriate Node.js project directory:

```bash
npm install
```

### 1.3. Make test scripts executable

For **ZSH**:

```bash
chmod 777 start-test.zsh run-all.zsh pull-logs.zsh start-test-guard.zsh
```

For **SH**:

```bash
chmod 777 start-test.sh run-all.sh pull-logs.sh start-test-guard.sh
```

---

## 2. Basic Version — Without GUARD

In this mode, the system runs **without bot detection mechanisms**.

### 2.1. Code configuration

Make sure the GUARD-related code is **commented out**.

#### `gielda/src/index.ts`

```typescript
// app.use(securityMiddleware);
```

#### `gielda/src/utils/activityMonitor.ts`

```typescript
// verifyUserActivity(info).catch(err => console.error("Error in bot protection:", err));
```

---

## 3. Configuring Load Tests

Tests are defined in the `params.txt` file.

### 3.1. General syntax

```bash
./start-test.[sh/zsh] [duration_seconds] [test_name] [number_of_users] [%ACTIVE_TRADER] [%CAUTIOUS_USER] [%SCRAPER_BOT]
```

Example:

```bash
./start-test.sh 3600 H1U500-49-50-1 500 49 50 1
```

A line beginning with `#` is disabled and will not be executed:

```bash
#./start-test.sh 3600 H1U500-49-50-1 500 49 50 1
```

### 3.2. Example test definitions

For **ZSH**:

```bash
./start-test.zsh 120 M2U200-45-45-10 200 45 45 10
```

For **SH**:

```bash
./start-test.sh 120 M2U200-45-45-10 200 45 45 10
```

Recommended pair for a 30-minute test:

```bash
# Without GUARD
./start-test.zsh 1800 M30U200-45-45-10 200 45 45 10

# With GUARD
./start-test-guard.zsh 1800 M30U200-45-45-10G 200 45 45 10
```

Equivalent **SH** example:

```bash
# Without GUARD
./start-test.sh 3600 H1U10-50-40-10 10 50 40 10

# With GUARD
./start-test-guard.sh 3600 H1U10-50-40-10G 10 50 40 10
```

> Use `start-test` for tests **without GUARD** and `start-test-guard` for tests **with GUARD**.

---

## 4. Starting the System

Run all configured tests with one of the following commands.

For **ZSH**:

```bash
./run-all.zsh
```

For **SH**:

```bash
./run-all.sh
```

---

## 5. ETL, Association, and Correlation Tests

After the load test generates an SQL file, move or copy that file to `Tests/main`.

### 5.1. Prepare the `Tests/main` directory

```bash
mkdir -p Tests/main
rm -f Tests/main/*.sql
cp M5U200-45-45-10.sql Tests/main/
```

Then enter the `Tests` directory:

```bash
cd Tests
```

Make the analysis script executable if needed.

For **ZSH**:

```bash
chmod 777 run_tests.zsh
```

For **SH**:

```bash
chmod 777 run_tests.sh
```

### 5.2. Run ETL and analysis

For **Windows PowerShell**:

```powershell
run_tests.ps1
```

For **Linux/macOS with ZSH**:

```bash
./run_tests.zsh
```

For **Linux/macOS with SH**:

```bash
./run_tests.sh
```

After the analysis finishes, a directory with the same name as the SQL file is created. It contains generated graphs and information about the test run.

> When running the version **without GUARD**, errors may appear after the `Analyzing blocked users` stage. This is expected because no GUARD blocking data is available.

---

## 6. Model Training

Go to:

```bash
cd Tests/models
```

Run one or more of the following training scripts.

### 6.1. Isolation Forest

```bash
python model_IsolationForest.py --dir M2U200-45-45-10
```

Generic form:

```bash
python model_IsolationForest.py --dir [data_directory_name_after_ETL]
```

### 6.2. One-Class SVM

```bash
python model_OC-SVM.py --dir M2U200-45-45-10
```

### 6.3. RCE

```bash
python model_RCE.py --dir M2U200-45-45-10
```

The RCE script saves the generated result directly to the weights directory.

### 6.4. XGBoost

Create or clean the analysis output directory if required:

```bash
mkdir -p analysisResults
rm -f analysisResults/*.png
```

Run training:

```bash
python model_XGBoost.py --dir M2U200-45-45-10
```

Example generated files:

```text
bot_xgboost_model_M2U200-45-45-10.json
bot_xgboost_encoders_M2U200-45-45-10.pkl
```

The encoders file contains data such as URL counts and one-hot encoding information.

---

## 7. Organizing Model Weights

Create the weights directory if necessary:

```bash
mkdir -p weights
```

Remove previous model files:

```bash
rm -f weights/*.pkl weights/*.json
```

Move selected model files:

```bash
mv \
  bot_gaussian_model_M2U200-45-45-10.pkl \
  bot_occ_modelM2U200-45-45-10.pkl \
  bot_ocsvm_model_M2U200-45-45-10.pkl \
  bot_xgboost_encoders_M2U200-45-45-10.pkl \
  bot_xgboost_model_M2U200-45-45-10.json \
  weights/
```

Alternatively, move all `.pkl` and `.json` files:

```bash
mv *.pkl *.json weights/
```

---

## 8. PCE / Model Visualization

Before running visualization scripts, update their input paths so that they point to the directory corresponding to the current test.

Visualization scripts:

```text
visualize_IsolationForest.py
visualize_OCSVM.py
visualize_RCE.py
visualize_XGBoost.py
```

Example configuration:

```python
INPUT_FILE = '../H1U10-50-40-10/merged_data.csv'
MODEL_FILE = './weights/bot_request_modelH1U10-50-40-10.json'
ENCODERS_FILE = './weights/bot_request_encoders_H1U10-50-40-10.pkl'
OUTPUT_DIR = '../H1U10-50-40-10/visualizations'
```

For another test, change the directory name accordingly, for example:

```text
M2U200-45-45-10
```

Run the visualization scripts:

```bash
python visualize_IsolationForest.py
python visualize_OCSVM.py
python visualize_RCE.py
python visualize_XGBoost.py
```

Example XGBoost outputs:

```text
../M2U200-45-45-10/visualizations/XGBoost_Boundary_Full_Stats.txt
../M2U200-45-45-10/visualizations/XGBoost_Boundary_Full.png
```

---

## 9. Predictive Version — GUARD

The GUARD version enables bot detection and uses the trained XGBoost model.

### 9.1. Enable GUARD in the application

The following lines must be **uncommented**.

#### `gielda/src/index.ts`

```typescript
app.use(securityMiddleware);
```

#### `gielda/src/utils/activityMonitor.ts`

```typescript
verifyUserActivity(info).catch(err => console.error("Error in bot protection:", err));
```

---

## 10. Configure the GUARD Model

The Guard module requires the XGBoost model weights and encoders.

Edit:

```text
traffic/bot_guard.py
```

Example:

```python
model.load_model("bot_xgboost_model_H1U200-45-45-10.json")
encoders_data = joblib.load("bot_xgboost_encoders_H1U200-45-45-10.pkl")
```

The referenced `.json` and `.pkl` files must be placed in the directory expected by `bot_guard.py`, typically the same `traffic` directory.

### 10.1. Configure the decision threshold

In `traffic/bot_guard.py`, update:

```python
BOT_THRESHOLD = 0.90
```

to the threshold determined during XGBoost training.

Example:

```text
Best threshold: 0.4504
```

Then configure:

```python
BOT_THRESHOLD = 0.4504
```

> The threshold should come from the training/evaluation results of the model being deployed.

---

## 11. Copy XGBoost Weights to GUARD

Before deploying a new model, remove previous GUARD weights:

```bash
rm -f traffic/*.pkl traffic/*.json
```

From the model weights directory, copy the required XGBoost files:

```bash
cp \
  bot_xgboost_encoders_M2U200-45-45-10.pkl \
  bot_xgboost_model_M2U200-45-45-10.json \
  ../../../traffic/
```

Alternative wildcard form:

```bash
cp bot_xgboost_*.pkl bot_xgboost_model*.json ../../../traffic/
```

If executed from the repository root, an equivalent command is:

```bash
cp \
  Tests/models/weights/bot_xgboost_*.pkl \
  Tests/models/weights/bot_xgboost_*.json \
  traffic/
```

---

## 12. Configure a GUARD Test

In `params.txt`, use `start-test-guard`.

For **ZSH**:

```bash
./start-test-guard.zsh 120 M2U200-45-45-10G 200 45 45 10
```

For **SH**:

```bash
./start-test-guard.sh 120 M2U200-45-45-10G 200 45 45 10
```

The `G` suffix can be used in the test name to distinguish GUARD tests from corresponding non-GUARD tests.

---

## 13. Start the System with GUARD

Return to the repository root and run:

For **ZSH**:

```bash
./run-all.zsh
```

For **SH**:

```bash
./run-all.sh
```

---

## 14. Analyze GUARD Test Results

Remove the previous SQL file from `Tests/main`:

```bash
rm -f Tests/main/*.sql
```

Copy the SQL file generated by the GUARD test:

```bash
cp M5U200-45-45-10G.sql Tests/main/
```

Run the test analysis again.

For **ZSH**:

```bash
cd Tests
./run_tests.zsh
```

For **SH**:

```bash
cd Tests
./run_tests.sh
```

---

## 15. End-to-End Example — Without GUARD

### Step 1: Disable GUARD

In `gielda/src/index.ts`:

```typescript
// app.use(securityMiddleware);
```

In `gielda/src/utils/activityMonitor.ts`:

```typescript
// verifyUserActivity(info).catch(err => console.error("Error in bot protection:", err));
```

### Step 2: Configure the test

Example `params.txt` entry:

```bash
./start-test.zsh 1800 M30U200-45-45-10 200 45 45 10
```

### Step 3: Start the system

```bash
./run-all.zsh
```

### Step 4: Prepare ETL input

```bash
mkdir -p Tests/main
rm -f Tests/main/*.sql
cp M30U200-45-45-10.sql Tests/main/
```

### Step 5: Run analysis

```bash
cd Tests
./run_tests.zsh
```

### Step 6: Train models

```bash
cd models

python model_IsolationForest.py --dir M30U200-45-45-10
python model_OC-SVM.py --dir M30U200-45-45-10
python model_RCE.py --dir M30U200-45-45-10
python model_XGBoost.py --dir M30U200-45-45-10
```

### Step 7: Run visualizations

Update the directory names inside the visualization scripts, then run:

```bash
python visualize_IsolationForest.py
python visualize_OCSVM.py
python visualize_RCE.py
python visualize_XGBoost.py
```

---

## 16. End-to-End Example — With GUARD

### Step 1: Enable GUARD

In `gielda/src/index.ts`:

```typescript
app.use(securityMiddleware);
```

In `gielda/src/utils/activityMonitor.ts`:

```typescript
verifyUserActivity(info).catch(err => console.error("Error in bot protection:", err));
```

### Step 2: Select the trained model

Example files:

```text
bot_xgboost_model_M2U200-45-45-10.json
bot_xgboost_encoders_M2U200-45-45-10.pkl
```

### Step 3: Copy the model to `traffic`

```bash
rm -f traffic/*.pkl traffic/*.json

cp \
  Tests/models/weights/bot_xgboost_*.pkl \
  Tests/models/weights/bot_xgboost_*.json \
  traffic/
```

### Step 4: Configure `traffic/bot_guard.py`

Example:

```python
model.load_model("bot_xgboost_model_M2U200-45-45-10.json")
encoders_data = joblib.load("bot_xgboost_encoders_M2U200-45-45-10.pkl")

BOT_THRESHOLD = 0.4504
```

### Step 5: Configure the GUARD test

In `params.txt`:

```bash
./start-test-guard.zsh 1800 M30U200-45-45-10G 200 45 45 10
```

### Step 6: Start the system

```bash
./run-all.zsh
```

### Step 7: Analyze results

```bash
rm -f Tests/main/*.sql
cp M30U200-45-45-10G.sql Tests/main/

cd Tests
./run_tests.zsh
```

---

## 17. Command Summary

### Without GUARD

```bash
./start-test.zsh ...
./run-all.zsh
./run_tests.zsh
```

or:

```bash
./start-test.sh ...
./run-all.sh
./run_tests.sh
```

### With GUARD

```bash
./start-test-guard.zsh ...
./run-all.zsh
./run_tests.zsh
```

or:

```bash
./start-test-guard.sh ...
./run-all.sh
./run_tests.sh
```

### Model training

```bash
python model_IsolationForest.py --dir <TEST_DIR>
python model_OC-SVM.py --dir <TEST_DIR>
python model_RCE.py --dir <TEST_DIR>
python model_XGBoost.py --dir <TEST_DIR>
```

### Visualization

```bash
python visualize_IsolationForest.py
python visualize_OCSVM.py
python visualize_RCE.py
python visualize_XGBoost.py
```

---

## 18. Important Notes

- Run load tests for at least **300 seconds** unless a shorter run is intentionally used only for a smoke test.
- Commented lines in `params.txt` are not executed.
- The application code must be configured consistently with the selected mode:
  - **without GUARD** → GUARD middleware and activity verification commented out;
  - **with GUARD** → GUARD middleware and activity verification enabled.
- Always deploy the XGBoost `.json` model together with the corresponding `.pkl` encoders.
- The `BOT_THRESHOLD` value must correspond to the threshold obtained for the deployed model.
- Remove old GUARD model files before copying a new model to avoid accidentally loading stale weights.
- Update visualization paths whenever the test directory changes.
- Keep GUARD and non-GUARD test names distinct, for example by adding the `G` suffix to GUARD test names.
