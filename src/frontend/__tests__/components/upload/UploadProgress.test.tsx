import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { UploadProgress } from '@/components/upload/UploadProgress';

describe('UploadProgress', () => {
  const defaultProps = {
    progress: 50,
    filename: 'tiktok-export.zip',
    bytesUploadedFormatted: '25 MB',
    bytesTotalFormatted: '50 MB',
  };

  it('renders progress bar with correct percentage', () => {
    render(<UploadProgress {...defaultProps} />);

    const progressBar = screen.getByRole('progressbar');
    expect(progressBar).toHaveAttribute('aria-valuenow', '50');
    expect(progressBar).toHaveAttribute('aria-valuemin', '0');
    expect(progressBar).toHaveAttribute('aria-valuemax', '100');
  });

  it('displays filename', () => {
    render(<UploadProgress {...defaultProps} />);

    expect(screen.getByText('tiktok-export.zip')).toBeInTheDocument();
  });

  it('displays bytes uploaded and total', () => {
    render(<UploadProgress {...defaultProps} />);

    expect(screen.getByText('25 MB / 50 MB')).toBeInTheDocument();
  });

  it('displays percentage', () => {
    render(<UploadProgress {...defaultProps} />);

    expect(screen.getByText('50%')).toBeInTheDocument();
  });

  it('shows cancel button by default', () => {
    const onCancel = vi.fn();
    render(<UploadProgress {...defaultProps} onCancel={onCancel} />);

    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    expect(cancelButton).toBeInTheDocument();
  });

  it('calls onCancel when cancel button is clicked', () => {
    const onCancel = vi.fn();
    render(<UploadProgress {...defaultProps} onCancel={onCancel} />);

    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    fireEvent.click(cancelButton);

    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('hides cancel button when isComplete is true', () => {
    const onCancel = vi.fn();
    render(
      <UploadProgress {...defaultProps} onCancel={onCancel} isComplete />
    );

    expect(
      screen.queryByRole('button', { name: /cancel/i })
    ).not.toBeInTheDocument();
  });

  it('displays "Complete" when isComplete is true', () => {
    render(<UploadProgress {...defaultProps} isComplete />);

    expect(screen.getByText('Complete')).toBeInTheDocument();
    expect(screen.queryByText('50%')).not.toBeInTheDocument();
  });

  it('clamps progress to 0-100 range', () => {
    const { rerender } = render(
      <UploadProgress {...defaultProps} progress={-10} />
    );

    let progressBar = screen.getByRole('progressbar');
    expect(progressBar).toHaveAttribute('aria-valuenow', '0');

    rerender(<UploadProgress {...defaultProps} progress={150} />);

    progressBar = screen.getByRole('progressbar');
    expect(progressBar).toHaveAttribute('aria-valuenow', '100');
  });

  it('applies custom className', () => {
    const { container } = render(
      <UploadProgress {...defaultProps} className="custom-class" />
    );

    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('shows loading spinner when not complete', () => {
    render(<UploadProgress {...defaultProps} />);

    // The Loader2 icon has animate-spin class
    const spinner = document.querySelector('.animate-spin');
    expect(spinner).toBeInTheDocument();
  });

  it('shows checkmark when complete', () => {
    render(<UploadProgress {...defaultProps} isComplete />);

    // When complete, checkmark SVG is shown instead of spinner
    const checkmark = document.querySelector('svg path[d*="5 13l4 4L19 7"]');
    expect(checkmark).toBeInTheDocument();
  });
});
