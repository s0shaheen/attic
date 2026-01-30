import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { TikTokUploader, uploadResultSchema } from '@/components/upload/TikTokUploader';
import { MAX_FILE_SIZE } from '@/lib/uppy/config';

// Mock the useUppy hook
const mockUseUppy = vi.fn();
vi.mock('@/hooks/useUppy', () => ({
  useUppy: (options: Record<string, unknown>) => mockUseUppy(options),
}));

describe('TikTokUploader', () => {
  const defaultMockState = {
    status: 'idle' as const,
    progress: 0,
    bytesUploaded: 0,
    bytesTotal: 0,
    filename: null,
    error: null,
  };

  const mockHook = {
    uppy: {},
    state: defaultMockState,
    addFile: vi.fn(),
    startUpload: vi.fn(),
    cancelUpload: vi.fn(),
    reset: vi.fn(),
    bytesUploadedFormatted: '0 Bytes',
    bytesTotalFormatted: '0 Bytes',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseUppy.mockReturnValue(mockHook);
  });

  describe('Initial State (Drop Zone)', () => {
    it('renders drag-and-drop zone', () => {
      const onUploadComplete = vi.fn();
      render(<TikTokUploader onUploadComplete={onUploadComplete} />);

      expect(
        screen.getByText(/Upload your TikTok export/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Drag and drop/i)
      ).toBeInTheDocument();
    });

    it('renders browse files button', () => {
      const onUploadComplete = vi.fn();
      render(<TikTokUploader onUploadComplete={onUploadComplete} />);

      expect(
        screen.getByRole('button', { name: /browse files/i })
      ).toBeInTheDocument();
    });

    it('shows file size limit', () => {
      const onUploadComplete = vi.fn();
      render(<TikTokUploader onUploadComplete={onUploadComplete} />);

      expect(screen.getByText(/500 MB/i)).toBeInTheDocument();
    });

    it('has hidden file input', () => {
      const onUploadComplete = vi.fn();
      render(<TikTokUploader onUploadComplete={onUploadComplete} />);

      const fileInput = screen.getByLabelText(/choose file/i);
      expect(fileInput).toHaveClass('hidden');
      expect(fileInput).toHaveAttribute('type', 'file');
      expect(fileInput).toHaveAttribute(
        'accept',
        '.zip,application/zip,application/x-zip-compressed'
      );
    });
  });

  describe('File Validation', () => {
    it('accepts valid ZIP files', async () => {
      const onUploadComplete = vi.fn();
      const onUploadError = vi.fn();
      render(
        <TikTokUploader
          onUploadComplete={onUploadComplete}
          onUploadError={onUploadError}
        />
      );

      const file = new File(['test'], 'export.zip', { type: 'application/zip' });
      const input = screen.getByLabelText(/choose file/i);

      fireEvent.change(input, { target: { files: [file] } });

      await waitFor(() => {
        expect(mockHook.addFile).toHaveBeenCalledWith(file);
      });
      expect(onUploadError).not.toHaveBeenCalled();
    });

    it('rejects non-ZIP files', async () => {
      const onUploadComplete = vi.fn();
      const onUploadError = vi.fn();
      render(
        <TikTokUploader
          onUploadComplete={onUploadComplete}
          onUploadError={onUploadError}
        />
      );

      const file = new File(['test'], 'document.pdf', {
        type: 'application/pdf',
      });
      const input = screen.getByLabelText(/choose file/i);

      fireEvent.change(input, { target: { files: [file] } });

      await waitFor(() => {
        expect(onUploadError).toHaveBeenCalled();
      });
      expect(mockHook.addFile).not.toHaveBeenCalled();
    });

    it('rejects files over max size', async () => {
      const onUploadComplete = vi.fn();
      const onUploadError = vi.fn();
      render(
        <TikTokUploader
          onUploadComplete={onUploadComplete}
          onUploadError={onUploadError}
        />
      );

      // Create a file larger than MAX_FILE_SIZE
      const largeContent = new Uint8Array(MAX_FILE_SIZE + 1);
      const file = new File([largeContent], 'export.zip', {
        type: 'application/zip',
      });
      Object.defineProperty(file, 'size', { value: MAX_FILE_SIZE + 1 });

      const input = screen.getByLabelText(/choose file/i);
      fireEvent.change(input, { target: { files: [file] } });

      await waitFor(() => {
        expect(onUploadError).toHaveBeenCalled();
      });
      expect(mockHook.addFile).not.toHaveBeenCalled();
    });
  });

  describe('File Selected State', () => {
    it('shows file info when file is selected', () => {
      const onUploadComplete = vi.fn();
      mockUseUppy.mockReturnValue({
        ...mockHook,
        state: {
          ...defaultMockState,
          filename: 'tiktok-export.zip',
          bytesTotal: 52428800,
        },
        bytesTotalFormatted: '50 MB',
      });

      render(<TikTokUploader onUploadComplete={onUploadComplete} />);

      expect(screen.getByText('tiktok-export.zip')).toBeInTheDocument();
      expect(screen.getByText('50 MB')).toBeInTheDocument();
    });

    it('shows upload and change buttons when file is selected', () => {
      const onUploadComplete = vi.fn();
      mockUseUppy.mockReturnValue({
        ...mockHook,
        state: {
          ...defaultMockState,
          filename: 'tiktok-export.zip',
          bytesTotal: 52428800,
        },
      });

      render(<TikTokUploader onUploadComplete={onUploadComplete} />);

      expect(
        screen.getByRole('button', { name: /upload/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /change/i })
      ).toBeInTheDocument();
    });

    it('calls startUpload when upload button is clicked', () => {
      const onUploadComplete = vi.fn();
      mockUseUppy.mockReturnValue({
        ...mockHook,
        state: {
          ...defaultMockState,
          filename: 'tiktok-export.zip',
        },
      });

      render(<TikTokUploader onUploadComplete={onUploadComplete} />);

      const uploadButton = screen.getByRole('button', { name: /upload/i });
      fireEvent.click(uploadButton);

      expect(mockHook.startUpload).toHaveBeenCalledTimes(1);
    });

    it('calls reset when change button is clicked', () => {
      const onUploadComplete = vi.fn();
      mockUseUppy.mockReturnValue({
        ...mockHook,
        state: {
          ...defaultMockState,
          filename: 'tiktok-export.zip',
        },
      });

      render(<TikTokUploader onUploadComplete={onUploadComplete} />);

      const changeButton = screen.getByRole('button', { name: /change/i });
      fireEvent.click(changeButton);

      expect(mockHook.reset).toHaveBeenCalledTimes(1);
    });
  });

  describe('Uploading State', () => {
    it('shows progress during upload', () => {
      const onUploadComplete = vi.fn();
      mockUseUppy.mockReturnValue({
        ...mockHook,
        state: {
          ...defaultMockState,
          status: 'uploading',
          filename: 'tiktok-export.zip',
          progress: 45,
          bytesUploaded: 23068672,
          bytesTotal: 52428800,
        },
        bytesUploadedFormatted: '22 MB',
        bytesTotalFormatted: '50 MB',
      });

      render(<TikTokUploader onUploadComplete={onUploadComplete} />);

      expect(screen.getByRole('progressbar')).toBeInTheDocument();
      expect(screen.getByText('45%')).toBeInTheDocument();
    });

    it('shows cancel button during upload', () => {
      const onUploadComplete = vi.fn();
      mockUseUppy.mockReturnValue({
        ...mockHook,
        state: {
          ...defaultMockState,
          status: 'uploading',
          filename: 'tiktok-export.zip',
        },
      });

      render(<TikTokUploader onUploadComplete={onUploadComplete} />);

      expect(
        screen.getByRole('button', { name: /cancel/i })
      ).toBeInTheDocument();
    });

    it('calls cancelUpload when cancel is clicked', () => {
      const onUploadComplete = vi.fn();
      mockUseUppy.mockReturnValue({
        ...mockHook,
        state: {
          ...defaultMockState,
          status: 'uploading',
          filename: 'tiktok-export.zip',
        },
      });

      render(<TikTokUploader onUploadComplete={onUploadComplete} />);

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      fireEvent.click(cancelButton);

      expect(mockHook.cancelUpload).toHaveBeenCalledTimes(1);
    });
  });

  describe('Complete State', () => {
    it('shows complete state with checkmark', () => {
      const onUploadComplete = vi.fn();
      mockUseUppy.mockReturnValue({
        ...mockHook,
        state: {
          ...defaultMockState,
          status: 'complete',
          filename: 'tiktok-export.zip',
          progress: 100,
          bytesTotal: 52428800,
        },
        bytesTotalFormatted: '50 MB',
      });

      render(<TikTokUploader onUploadComplete={onUploadComplete} />);

      expect(screen.getByText('Complete')).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('shows error component on error', () => {
      const onUploadComplete = vi.fn();
      mockUseUppy.mockReturnValue({
        ...mockHook,
        state: {
          ...defaultMockState,
          status: 'error',
          error: new Error('Upload failed'),
        },
      });

      render(<TikTokUploader onUploadComplete={onUploadComplete} />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Upload Failed')).toBeInTheDocument();
    });

    it('calls reset when retry is clicked', () => {
      const onUploadComplete = vi.fn();
      mockUseUppy.mockReturnValue({
        ...mockHook,
        state: {
          ...defaultMockState,
          status: 'error',
          error: new Error('Upload failed'),
        },
      });

      render(<TikTokUploader onUploadComplete={onUploadComplete} />);

      const retryButton = screen.getByRole('button', { name: /try again/i });
      fireEvent.click(retryButton);

      expect(mockHook.reset).toHaveBeenCalledTimes(1);
    });
  });

  describe('Disabled State', () => {
    it('disables browse button when disabled', () => {
      const onUploadComplete = vi.fn();
      render(<TikTokUploader onUploadComplete={onUploadComplete} disabled />);

      const browseButton = screen.getByRole('button', { name: /browse/i });
      expect(browseButton).toBeDisabled();
    });

    it('disables file input when disabled', () => {
      const onUploadComplete = vi.fn();
      render(<TikTokUploader onUploadComplete={onUploadComplete} disabled />);

      const fileInput = screen.getByLabelText(/choose file/i);
      expect(fileInput).toBeDisabled();
    });
  });

  describe('uploadResultSchema', () => {
    it('validates valid upload result', () => {
      const result = uploadResultSchema.safeParse({
        uploadId: '123e4567-e89b-12d3-a456-426614174000',
        storagePath: 'user-id/upload-id.zip',
        filename: 'export.zip',
      });
      expect(result.success).toBe(true);
    });

    it('rejects invalid UUID', () => {
      const result = uploadResultSchema.safeParse({
        uploadId: 'not-a-uuid',
        storagePath: 'user-id/upload-id.zip',
        filename: 'export.zip',
      });
      expect(result.success).toBe(false);
    });
  });
});
