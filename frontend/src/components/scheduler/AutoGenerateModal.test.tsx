import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { AutoGenerateModal } from './AutoGenerateModal';
import { Branch } from '../../types';

describe('AutoGenerateModal Component', () => {
  const mockBranches: Branch[] = [
    {
      id: 1,
      department: 1,
      department_name: 'Computer Science',
      code: 'BTECH_CSE',
      name: 'B.Tech CSE',
      degree_name: 'B.Tech',
      max_semesters: 8,
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
    {
      id: 2,
      department: 1,
      department_name: 'Computer Science',
      code: 'BTECH_ECE',
      name: 'B.Tech ECE',
      degree_name: 'B.Tech',
      max_semesters: 8,
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
  ];

  it('does not render when isOpen is false', () => {
    const { container } = render(
      <AutoGenerateModal
        isOpen={false}
        onClose={vi.fn()}
        branches={mockBranches}
        onStartGeneration={vi.fn()}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders modal with target branches and default settings when open', () => {
    render(
      <AutoGenerateModal
        isOpen={true}
        onClose={vi.fn()}
        branches={mockBranches}
        onStartGeneration={vi.fn()}
      />
    );

    expect(screen.getByText('Smart Auto-Scheduling')).toBeInTheDocument();
    expect(screen.getByText('BTECH_CSE')).toBeInTheDocument();
    expect(screen.getByText('BTECH_ECE')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /start auto-scheduling/i })).toBeInTheDocument();
  });

  it('toggles Deselect All and shows error when submitting with 0 selected branches', () => {
    render(
      <AutoGenerateModal
        isOpen={true}
        onClose={vi.fn()}
        branches={mockBranches}
        onStartGeneration={vi.fn()}
      />
    );

    const selectAllBtn = screen.getByRole('button', { name: /deselect all/i });
    fireEvent.click(selectAllBtn); // Deselects all branches

    const submitBtn = screen.getByRole('button', { name: /start auto-scheduling/i });
    fireEvent.click(submitBtn);

    expect(screen.getByText(/please select at least one branch/i)).toBeInTheDocument();
  });

  it('submits generation config with selected branch IDs and time limit', () => {
    const mockStart = vi.fn();

    render(
      <AutoGenerateModal
        isOpen={true}
        onClose={vi.fn()}
        branches={mockBranches}
        onStartGeneration={mockStart}
      />
    );

    const submitBtn = screen.getByRole('button', { name: /start auto-scheduling/i });
    fireEvent.click(submitBtn);

    expect(mockStart).toHaveBeenCalledWith({
      branch_ids: [1, 2],
      time_limit: 60,
      replace_existing: true,
    });
  });

  it('displays loading indicator and disables submit button when isLoading is true', () => {
    render(
      <AutoGenerateModal
        isOpen={true}
        onClose={vi.fn()}
        branches={mockBranches}
        onStartGeneration={vi.fn()}
        isLoading={true}
      />
    );

    const submitBtn = screen.getByRole('button', { name: /starting generator.../i });
    expect(submitBtn).toBeDisabled();
  });
});
