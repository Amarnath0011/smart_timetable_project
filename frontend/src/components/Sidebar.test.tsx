import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import * as useAuthHook from '../hooks/useAuth';

vi.mock('../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}));

describe('Sidebar Component Role-Based Navigation', () => {
  it('renders Super Admin navigation links including Departments and Audits', () => {
    vi.mocked(useAuthHook.useAuth).mockReturnValue({
      user: {
        id: 1,
        email: 'admin@university.edu',
        full_name: 'Admin User',
        is_active: true,
        is_staff: true,
        is_superuser: true,
        roles: ['SUPER_ADMIN'],
        role_assignments: [],
        created_at: '2026-01-01T00:00:00Z',
      },
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      hasRole: vi.fn(),
      refreshUser: vi.fn(),
    });

    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    );

    expect(screen.getByText('Admin Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Departments')).toBeInTheDocument();
    expect(screen.getByText('Rooms & Facilities')).toBeInTheDocument();
    expect(screen.getByText('Audit Trail Logs')).toBeInTheDocument();
  });

  it('renders Coordinator navigation while hiding Super Admin exclusive links', () => {
    vi.mocked(useAuthHook.useAuth).mockReturnValue({
      user: {
        id: 2,
        email: 'coord@university.edu',
        full_name: 'CSE Coordinator',
        is_active: true,
        is_staff: false,
        is_superuser: false,
        roles: ['BRANCH_COORDINATOR'],
        role_assignments: [],
        created_at: '2026-01-01T00:00:00Z',
      },
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      hasRole: vi.fn(),
      refreshUser: vi.fn(),
    });

    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    );

    expect(screen.getByText('Coordinator Desk')).toBeInTheDocument();
    expect(screen.getByText('Timetable Planner')).toBeInTheDocument();
    expect(screen.getByText('Course Catalog')).toBeInTheDocument();

    // Admin-only links must be absent
    expect(screen.queryByText('Departments')).not.toBeInTheDocument();
    expect(screen.queryByText('Audit Trail Logs')).not.toBeInTheDocument();
  });

  it('renders Professor navigation showing My Teaching Schedule and hiding Planner', () => {
    vi.mocked(useAuthHook.useAuth).mockReturnValue({
      user: {
        id: 3,
        email: 'prof@university.edu',
        full_name: 'Dr. Sharma',
        is_active: true,
        is_staff: false,
        is_superuser: false,
        roles: ['PROFESSOR'],
        role_assignments: [],
        created_at: '2026-01-01T00:00:00Z',
      },
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      hasRole: vi.fn(),
      refreshUser: vi.fn(),
    });

    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    );

    expect(screen.getByText('Faculty Portal')).toBeInTheDocument();
    expect(screen.getByText('My Teaching Schedule')).toBeInTheDocument();

    // Coordinator & Admin links must be hidden
    expect(screen.queryByText('Timetable Planner')).not.toBeInTheDocument();
    expect(screen.queryByText('Departments')).not.toBeInTheDocument();
  });
});
