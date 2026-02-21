#!/bin/bash

# YouTube RAG Chatbot Setup Script

echo "🎬 YouTube RAG Chatbot - Setup Script"
echo "======================================"
echo ""

# Check Python version
echo "📋 Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $python_version"

# Create virtual environment
echo ""
echo "🔨 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "✅ Virtual environment created"
echo ""
echo "📦 Installing dependencies..."

# Activate and install
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Dependencies installed"
echo ""

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your OPENROUTER_API_KEY"
else
    echo "✅ .env file already exists"
fi

# Create static directory
echo ""
echo "📁 Setting up directories..."
mkdir -p static

# Move index.html if it exists in root
if [ -f index.html ]; then
    mv index.html static/
    echo "✅ Moved index.html to static/"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your OPENROUTER_API_KEY"
echo "2. Install Chrome extension from chrome://extensions/"
echo "3. Run: source venv/bin/activate"
echo "4. Run: python app.py"
echo ""
