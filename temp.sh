# 1. Create the missing folders + placeholder files Harbor expects
mkdir -p solution tests
touch solution/solve.sh tests/test_outputs.py tests/test.sh
chmod +x solution/solve.sh tests/test.sh

# 2. Fix the case of instruction.md if it's uppercase
# (macOS is case-insensitive so we have to two-step it)
[ -f instruction.MD ] && mv instruction.MD instruction.tmp && mv instruction.tmp instruction.md

# 3. Verify
ls -la
test -f instruction.md && echo "✓ instruction.md" || echo "✗"
test -d tests && echo "✓ tests/" || echo "✗"
test -d solution && echo "✓ solution/" || echo "✗"
