## Pull Request Template

### Description
Brief description of the changes made in this PR.

### Type of Change
- [ ] 🆕 New feature
- [ ] 🐛 Bug fix
- [ ] 📚 Documentation update
- [ ] 🔧 Code refactoring
- [ ] 🧪 Test improvements
- [ ] 🔒 Security enhancement
- [ ] ⚡ Performance improvement

### Role-Based Access Control (RBAC) Checklist
- [ ] RBAC logic is properly implemented for new features
- [ ] Host-only functionality is restricted appropriately
- [ ] Frontend UI reflects role-based permissions
- [ ] Unauthorized access attempts return proper error responses
- [ ] Both host and listener roles have been tested

### Testing Checklist
- [ ] All existing tests pass
- [ ] New tests added for new functionality
- [ ] Socket.IO events tested (if applicable)
- [ ] Authentication flows tested
- [ ] Frontend functionality tested in browser
- [ ] Error handling tested

### Documentation Checklist
- [ ] Code is properly documented with docstrings
- [ ] README.md updated (if needed)
- [ ] API changes documented
- [ ] Environment variables documented (if new ones added)

### Environment & Dependencies
- [ ] No new dependencies added without justification
- [ ] Requirements files updated (if dependencies changed)
- [ ] Environment variables added to `.env.example` (if applicable)
- [ ] Docker configuration updated (if needed)

### Security Checklist
- [ ] No sensitive information exposed in code
- [ ] Authentication properly implemented
- [ ] Authorization checks in place
- [ ] Input validation implemented
- [ ] Error messages don't leak sensitive information

### Frontend Checklist (if applicable)
- [ ] UI is responsive and user-friendly
- [ ] Role-based UI elements work correctly
- [ ] Socket.IO connections handled properly
- [ ] Error states displayed to users
- [ ] Accessibility considerations addressed

### How to Test
1. Steps to test the changes:
   - 
   - 
   - 

2. Test different user roles:
   - [ ] Tested as host user
   - [ ] Tested as listener user
   - [ ] Tested as unauthenticated user

### Screenshots (if applicable)
<!-- Add screenshots of UI changes -->

### Additional Notes
<!-- Any additional information, concerns, or context -->

### Related Issues
Closes #<!-- issue number -->
