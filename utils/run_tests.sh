#!/bin/bash

cd $(dirname $0)/..

echo "=== Nuking old .pyc files..."
find vumidash/ -name '*.pyc' -delete
echo "=== Erasing previous coverage data..."
coverage erase
echo "=== Running trial tests..."
coverage run ./ve/bin/trial --reporter=subunit vumidash | tee results.txt | subunit2junitxml > test_results.xml
subunit2pyunit < results.txt
rm results.txt
echo "=== Processing coverage data..."
coverage xml
echo "=== Checking for PEP-8 violations..."
pep8 --repeat vumidash > pep8.txt
echo "=== Done."
