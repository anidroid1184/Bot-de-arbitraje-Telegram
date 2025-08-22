#!/bin/bash
# Test workflow for Betburger bot - all 6 tabs
# Usage: ./scripts/test_all_tabs.sh

set -e

echo "🚀 Starting Betburger 6-tab test workflow..."

# Step 1: Run smoke + select filters (opens session, selects filters, sends "filter opened" alerts)
echo "📋 Step 1/2: Opening session and selecting filters..."
python3 -m scripts.run_smoke_and_select

# Brief pause to ensure all filters are selected
echo "⏳ Waiting 3 seconds for filters to stabilize..."
sleep 3

# Step 2: Extract and send real results from all 6 tabs
echo "📊 Step 2/2: Extracting and sending real results from all tabs..."
python3 -m scripts.betburger_send_all_tabs_results

echo "✅ Test workflow completed!"
echo "📱 Check your Telegram channels for:"
echo "   - Filter opened alerts (from step 1)"
echo "   - Real betting data summaries (from step 2)"
