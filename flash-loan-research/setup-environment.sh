#!/bin/bash

# Flash Loan Research Environment Setup Script

echo "🚀 Setting up environment for Flash Loan Research..."

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✅ Created .env file from template"
    echo "⚠️  Please edit .env file with your actual API keys before running the application"
else
    echo "✅ .env file already exists"
fi

# Check if API keys are properly configured
if grep -q "your_" .env; then
    echo "⚠️  WARNING: .env file contains placeholder values - please update with actual API keys"
    echo ""
    echo "🔑 Required API Keys:"
    echo "   - Infura API Key (get from https://infura.io/)"
    echo "   - Dune Analytics API Key (get from https://dune.com/)"
    echo "   - The Graph API Key (get from https://thegraph.com/)"
    echo ""
    echo "📋 Update these placeholder values in .env file:"
    grep "your_" .env
else
    echo "✅ API keys appear to be configured"
fi

echo ""
echo "🎯 Environment Setup Complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your actual API keys"
echo "2. Run 'npm install' to install dependencies"
echo "3. Run 'npm start' to start the application"