# Contributing to BeatSync Mixer

Thank you for your interest in contributing to BeatSync Mixer! This document provides guidelines for contributing to the project.

## Development Workflow

### Branch Strategy
- **main**: Production-ready code
- **develop**: Integration branch for features
- **feature/**: Feature branches (e.g., `feature/rbac`, `feature/playlist-export`)
- **bugfix/**: Bug fix branches (e.g., `bugfix/socket-disconnect`)
- **hotfix/**: Critical production fixes

### Getting Started
1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/beatsync-mixer.git`
3. Create a feature branch: `git checkout -b feature/your-feature-name`
4. Set up the development environment (see README.md)

### Making Changes
1. Make your changes in small, logical commits
2. Write clear, descriptive commit messages
3. Add tests for new functionality
4. Ensure all tests pass: `python -m pytest`
5. Update documentation if needed

### Commit Message Guidelines
Use the conventional commit format:
```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
```
feat(rbac): implement role-based access control
fix(spotify): handle expired tokens gracefully
docs(readme): update setup instructions
```

### Pull Request Process
1. Ensure your branch is up to date with the target branch
2. Create a pull request using the provided template
3. Fill out all sections of the PR template
4. Request review from maintainers
5. Address any feedback promptly

### Code Standards
- Follow Python PEP 8 style guidelines
- Use meaningful variable and function names
- Add docstrings for functions and classes
- Keep functions small and focused
- Write tests for new functionality

### Testing
- Write unit tests for backend logic
- Test Socket.IO events and authentication
- Test role-based access control scenarios
- Ensure frontend functionality works across browsers

### Role-Based Access Control (RBAC)
When working with RBAC features:
- Test both host and listener roles
- Verify unauthorized access is properly blocked
- Update frontend UI to reflect role restrictions
- Document any new role-based features

### Environment Setup
- Copy `.env.example` to `.env` and configure your credentials
- Set `HOST_SPOTIFY_ID` to your Spotify ID for testing host features
- Use different Spotify accounts to test listener functionality

## Questions?
If you have questions about contributing, please:
1. Check existing issues and discussions
2. Create a new issue with the "question" label
3. Reach out to maintainers

Thank you for contributing to BeatSync Mixer!
