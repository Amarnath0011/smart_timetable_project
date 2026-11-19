import { describe, it, expect } from 'vitest';
import { getDashboardForUser } from './AuthContext';
import { User } from '../types';

describe('AuthContext - getDashboardForUser helper', () => {
  const baseUser: User = {
    id: 1,
    email: 'test@university.edu',
    full_name: 'Test User',
    is_active: true,
    is_staff: false,
    is_superuser: false,
    roles: [],
    role_assignments: [],
    created_at: '2026-01-01T00:00:00Z',
  };

  it('routes SUPER_ADMIN to /dashboard/admin', () => {
    const adminUser: User = {
      ...baseUser,
      roles: ['SUPER_ADMIN'],
    };
    expect(getDashboardForUser(adminUser)).toBe('/dashboard/admin');
  });

  it('routes is_superuser to /dashboard/admin even without explicit role', () => {
    const superUser: User = {
      ...baseUser,
      is_superuser: true,
    };
    expect(getDashboardForUser(superUser)).toBe('/dashboard/admin');
  });

  it('routes BRANCH_COORDINATOR to /dashboard/coordinator', () => {
    const coordUser: User = {
      ...baseUser,
      roles: ['BRANCH_COORDINATOR'],
    };
    expect(getDashboardForUser(coordUser)).toBe('/dashboard/coordinator');
  });

  it('routes PROFESSOR to /dashboard/professor', () => {
    const profUser: User = {
      ...baseUser,
      roles: ['PROFESSOR'],
    };
    expect(getDashboardForUser(profUser)).toBe('/dashboard/professor');
  });

  it('defaults to /dashboard/admin for fallback role handling', () => {
    const plainUser: User = {
      ...baseUser,
      roles: [],
    };
    expect(getDashboardForUser(plainUser)).toBe('/dashboard/admin');
  });
});
