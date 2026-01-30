import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { UploadError } from '@/components/upload/UploadError';

describe('UploadError', () => {
  it('renders error message', () => {
    render(<UploadError error={new Error('Test error message')} />);

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Upload Failed')).toBeInTheDocument();
  });

  it('displays user-friendly message for file type errors', () => {
    render(<UploadError error={new Error('File type not allowed')} />);

    expect(
      screen.getByText(/Please select a ZIP file/i)
    ).toBeInTheDocument();
  });

  it('displays user-friendly message for file size errors', () => {
    render(<UploadError error={new Error('File size too large')} />);

    expect(
      screen.getByText(/file is too large/i)
    ).toBeInTheDocument();
  });

  it('displays user-friendly message for authentication errors', () => {
    render(<UploadError error={new Error('Not authenticated')} />);

    expect(
      screen.getByText(/Please sign in to upload/i)
    ).toBeInTheDocument();
  });

  it('displays user-friendly message for upload limit errors', () => {
    render(<UploadError error={new Error('Upload limit exceeded')} />);

    expect(
      screen.getByText(/reached your upload limit/i)
    ).toBeInTheDocument();
  });

  it('displays user-friendly message for network errors', () => {
    render(<UploadError error={new Error('Network connection lost')} />);

    expect(
      screen.getByText(/Network error/i)
    ).toBeInTheDocument();
  });

  it('displays user-friendly message for timeout errors', () => {
    render(<UploadError error={new Error('Request timed out')} />);

    expect(
      screen.getByText(/Upload timed out/i)
    ).toBeInTheDocument();
  });

  it('displays original message for unknown errors', () => {
    render(<UploadError error={new Error('Some unique error')} />);

    expect(screen.getByText('Some unique error')).toBeInTheDocument();
  });

  it('shows retry button when onRetry is provided', () => {
    const onRetry = vi.fn();
    render(<UploadError error={new Error('Test')} onRetry={onRetry} />);

    expect(
      screen.getByRole('button', { name: /try again/i })
    ).toBeInTheDocument();
  });

  it('calls onRetry when retry button is clicked', () => {
    const onRetry = vi.fn();
    render(<UploadError error={new Error('Test')} onRetry={onRetry} />);

    const retryButton = screen.getByRole('button', { name: /try again/i });
    fireEvent.click(retryButton);

    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('shows dismiss button when onDismiss is provided', () => {
    const onDismiss = vi.fn();
    render(<UploadError error={new Error('Test')} onDismiss={onDismiss} />);

    expect(
      screen.getByRole('button', { name: /dismiss/i })
    ).toBeInTheDocument();
  });

  it('calls onDismiss when dismiss button is clicked', () => {
    const onDismiss = vi.fn();
    render(<UploadError error={new Error('Test')} onDismiss={onDismiss} />);

    const dismissButton = screen.getByRole('button', { name: /dismiss/i });
    fireEvent.click(dismissButton);

    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it('hides retry button when onRetry is not provided', () => {
    render(<UploadError error={new Error('Test')} />);

    expect(
      screen.queryByRole('button', { name: /try again/i })
    ).not.toBeInTheDocument();
  });

  it('hides dismiss button when onDismiss is not provided', () => {
    render(<UploadError error={new Error('Test')} />);

    expect(
      screen.queryByRole('button', { name: /dismiss/i })
    ).not.toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(
      <UploadError error={new Error('Test')} className="custom-class" />
    );

    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('has error alert role for accessibility', () => {
    render(<UploadError error={new Error('Test')} />);

    expect(screen.getByRole('alert')).toBeInTheDocument();
  });
});
