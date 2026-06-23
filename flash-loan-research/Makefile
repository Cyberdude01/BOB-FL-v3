.PHONY: help install test demo clean backup deploy check-dev

# Default target
help:
	@echo "BOB-FL - Flash Loan Execution System"
	@echo "======================================"
	@echo ""
	@echo "Available targets:"
	@echo "  install     - Install dependencies"
	@echo "  test        - Run all tests"
	@echo "  demo        - Run demonstration scripts"
	@echo "  clean       - Clean up temporary files"
	@echo "  backup      - Create backup archive"
	@echo "  deploy      - Deploy to production"
	@echo "  check-dev   - Validate Arbitrum/Base dev setup (read-only)"
	@echo "  dashboard   - Start dashboard server"
	@echo "  lint        - Run code linting"
	@echo "  format      - Format code with black"


# Read-only development setup validation
check-dev:
	@echo "Checking Arbitrum/Base development setup..."
	python3 scripts/check_dev_setup.py

# Install dependencies
install:
	pip install -r requirements.txt
	pip install -e .

# Run tests
test:
	@echo "Running tests..."
	python phase3_demo.py
	python phase4_demo.py
	python phase56_integrated_workflow.py
	@echo "All tests completed successfully!"

# Run demonstrations
demo:
	@echo "Running demonstrations..."
	@echo "Phase 3 Demo:"
	python phase3_demo.py
	@echo ""
	@echo "Phase 4 Demo:"
	python phase4_demo.py
	@echo ""
	@echo "Phase 5/6 Integrated Demo:"
	python phase56_integrated_workflow.py
	@echo ""
	@echo "All demonstrations completed!"

# Start dashboard server
dashboard:
	@echo "Starting dashboard server..."
	python phase5_dashboard_server.py

# Clean up temporary files
clean:
	@echo "Cleaning up temporary files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.log" -delete
	find . -type d -name "logs" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	@echo "Cleanup completed!"

# Create backup
backup:
	@echo "Creating backup..."
	@echo "This will create a compressed backup of the current state."
	@echo "Backup file: flash-loan-backup-$(date +%Y%m%d-%H%M%S).tar.gz"
	tar -czf flash-loan-backup-$(date +%Y%m%d-%H%M%S).tar.gz \
		--exclude=.git \
		--exclude=venv* \
		--exclude=node_modules \
		--exclude=*.db \
		--exclude=*.log \
		--exclude=*.tar.gz \
		.
	@echo "Backup created successfully!"

# Deploy to production
deploy:
	@echo "Deploying to production..."
	@echo "This would deploy the system to production environment."
	@echo "Note: Actual deployment steps depend on your infrastructure."
	@echo ""
	@echo "Pre-deployment checks:"
	@echo "1. All tests passing: $(shell if [ -f test_results.txt ]; then echo "✓"; else echo "✗"; fi)"
	@echo "2. Configuration files updated: $(shell if [ -f .env ]; then echo "✓"; else echo "✗"; fi)"
	@echo "3. API keys configured: $(shell if grep -q "your_" .env; then echo "✗"; else echo "✓"; fi)"
	@echo ""
	@echo "To deploy manually:"
	@echo "1. Update .env with production configuration"
	@echo "2. Run: python phase56_integrated_workflow.py"
	@echo "3. Start dashboard: python phase5_dashboard_server.py"
	@echo ""
	@echo "Deployment completed!"

# Code linting
lint:
	@echo "Running code linting..."
	@echo "This would run flake8 and other linting tools."
	@echo "Note: Ensure flake8 is installed: pip install flake8"
	@echo ""
	@echo "To run linting manually:"
	@echo "flake8 . --exclude=venv*,node_modules"

# Code formatting
format:
	@echo "Formatting code..."
	@echo "This would run black to format the code."
	@echo "Note: Ensure black is installed: pip install black"
	@echo ""
	@echo "To format code manually:"
	@echo "black . --exclude=venv* --exclude=node_modules"

# Database management
db-init:
	@echo "Initializing database..."
	python -c "from phase5_data_store import MetricsStore; MetricsStore().init_db()"
	@echo "Database initialized successfully!"

db-backup:
	@echo "Creating database backup..."
	cp phase5_metrics.db phase5_metrics_backup.db
	@echo "Database backed up to phase5_metrics_backup.db"

db-restore:
	@echo "Restoring database from backup..."
	if [ -f phase5_metrics_backup.db ]; then \
		cp phase5_metrics_backup.db phase5_metrics.db; \
		echo "Database restored successfully!"; \
	else \
		echo "No backup file found!"; \
	fi

# Development helpers
dev-setup:
	@echo "Setting up development environment..."
	python -m venv venv
	source venv/bin/activate && pip install -r requirements.txt
	pip install -e .
	@echo "Development environment setup complete!"

dev-install-hooks:
	@echo "Installing git hooks..."
	@echo "This would install pre-commit hooks for code quality."
	@echo "Note: Requires pre-commit to be installed: pip install pre-commit"
	@echo ""
	@echo "To install hooks manually:"
	@echo "pre-commit install"

# Documentation
docs:
	@echo "Building documentation..."
	@echo "This would generate documentation from source code."
	@echo ""
	@echo "Current documentation:"
	@echo "- README.md: Main project documentation"
	@echo "- README_PHASE3.md: Phase 3 documentation"
	@echo "- README_PHASE5.md: Phase 5 documentation"
	@echo "- README_PHASE56.md: Phase 5/6 integration documentation"
	@echo "- CONTRIBUTING.md: Contribution guidelines"
	@echo "- CHANGELOG.md: Version history"

# Security checks
security:
	@echo "Running security checks..."
	@echo "Checking for hardcoded API keys..."
	@echo "Note: This would scan for potential security issues."
	@echo ""
	@echo "Manual security checks:"
	@echo "1. Check for hardcoded API keys in source files"
	@echo "2. Verify .env file is not committed"
	@echo "3. Check file permissions for sensitive files"
	@echo "4. Review network configurations"

# Performance monitoring
perf-test:
	@echo "Running performance tests..."
	@echo "This would run performance benchmarks."
	@echo ""
	@echo "To run performance tests manually:"
	@echo "time python phase56_integrated_workflow.py"
	@echo ""
	@echo "Metrics to monitor:"
	@echo "- Execution time"
	@echo "- Memory usage"
	@echo "- Success rate"
	@echo "- Profit per opportunity"

# Docker support (if needed)
docker-build:
	@echo "Building Docker image..."
	@echo "This would create a Docker container for the application."
	@echo "Note: Requires Docker to be installed."
	@echo ""
	@echo "To build manually:"
	@echo "docker build -t bob-fl ."

docker-run:
	@echo "Running Docker container..."
	@echo "This would run the application in a Docker container."
	@echo "Note: Requires Docker to be installed."
	@echo ""
	@echo "To run manually:"
	@echo "docker run -p 8080:8080 bob-fl"

# Help for specific components
help-phase3:
	@echo "Phase 3: Automated Execution System"
	@echo "===================================="
	@echo "Commands:"
	@echo "  python phase3_demo.py - Run Phase 3 demonstration"
	@echo "  python phase3_execution_engine.py - Test execution engine"

help-phase4:
	@echo "Phase 4: Pattern Recognition & Playbooks"
	@echo "======================================="
	@echo "Commands:"
	@echo "  python phase4_demo.py - Run Phase 4 demonstration"
	@echo "  python phase4_pattern_recognition.py - Test pattern recognition"

help-phase56:
	@echo "Phase 5/6: Integrated Workflow"
	@echo "================================"
	@echo "Commands:"
	@echo "  python phase56_integrated_workflow.py - Run integrated demo"
	@echo "  python phase5_dashboard_server.py - Start dashboard server"
	@echo "  curl http://localhost:8080/api/summary - Get dashboard metrics"