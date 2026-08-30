#!/usr/bin/env bash
set -e

echo "================================================================================"
echo "DEMONSTRATION: CRYPTOGRAPHIC EVIDENCE INTEGRITY & TAMPER DETECTION"
echo "================================================================================"

SOURCE_CAPSULE="capsules/case-01.zip"
TEMP_DIR="scratch/tamper_demo"
TAMPERED_ZIP="scratch/case-01-tampered.zip"

rm -rf scratch
mkdir -p "$TEMP_DIR"

echo ""
echo "[1] Extracting legitimate reproduction capsule: $SOURCE_CAPSULE..."
unzip -q "$SOURCE_CAPSULE" -d "$TEMP_DIR"

echo "[2] Simulating adversary/malicious edit: Hand-editing manifest.json..."
echo "    -> Changing pre-patch retries_per_request from 7.0 to 3.0 to fake lower amplification"
sed -i 's/"retries_per_request": 7.0/"retries_per_request": 3.0/g' "$TEMP_DIR/manifest.json"

echo "[3] Repackaging tampered archive to $TAMPERED_ZIP..."
(cd "$TEMP_DIR" && zip -q -r "../../$TAMPERED_ZIP" .)

echo ""
echo "================================================================================"
echo "TEST A: REPLAYING TAMPERED CAPSULE (EXPECTED: LOUD TAMPER DETECTION FAILURE)"
echo "================================================================================"
set +e
python -m changeproof.replay "$TAMPERED_ZIP"
TAMPER_EXIT=$?
set -e
echo "Exit Code for Tampered Capsule: $TAMPER_EXIT (Non-zero indicates loud failure)"

echo ""
echo "================================================================================"
echo "TEST B: REPLAYING ORIGINAL UNTOUCHED CAPSULE (EXPECTED: PASS)"
echo "================================================================================"
python -m changeproof.replay "$SOURCE_CAPSULE"
CLEAN_EXIT=$?
echo "Exit Code for Untouched Capsule: $CLEAN_EXIT (0 indicates success)"

rm -rf scratch
echo ""
echo "================================================================================"
echo "TAMPER DETECTION DEMO COMPLETED SUCCESSFULLY"
echo "================================================================================"
