import { describe, it, expect } from 'vitest';
import {
  createUppyInstance,
  isValidZipFile,
  formatBytes,
  MAX_FILE_SIZE,
  ALLOWED_FILE_TYPES,
  ALLOWED_EXTENSIONS,
} from '@/lib/uppy/config';

describe('Uppy Config', () => {
  describe('createUppyInstance', () => {
    it('creates an Uppy instance with correct restrictions', () => {
      const uppy = createUppyInstance();

      expect(uppy).toBeDefined();
      expect(uppy.opts.restrictions).toBeDefined();
      expect(uppy.opts.restrictions?.maxFileSize).toBe(MAX_FILE_SIZE);
      expect(uppy.opts.restrictions?.maxNumberOfFiles).toBe(1);
      expect(uppy.opts.restrictions?.allowedFileTypes).toEqual([...ALLOWED_FILE_TYPES]);

      // Cleanup
      uppy.cancelAll();
    });

    it('creates instance with autoProceed disabled', () => {
      const uppy = createUppyInstance();

      expect(uppy.opts.autoProceed).toBe(false);

      uppy.cancelAll();
    });

    it('creates instance with single batch mode', () => {
      const uppy = createUppyInstance();

      expect(uppy.opts.allowMultipleUploadBatches).toBe(false);

      uppy.cancelAll();
    });
  });

  describe('isValidZipFile', () => {
    it('returns true for application/zip MIME type', () => {
      const file = new File(['test'], 'export.zip', { type: 'application/zip' });
      expect(isValidZipFile(file)).toBe(true);
    });

    it('returns true for application/x-zip-compressed MIME type', () => {
      const file = new File(['test'], 'export.zip', {
        type: 'application/x-zip-compressed',
      });
      expect(isValidZipFile(file)).toBe(true);
    });

    it('returns true for application/octet-stream with .zip extension', () => {
      const file = new File(['test'], 'export.zip', {
        type: 'application/octet-stream',
      });
      expect(isValidZipFile(file)).toBe(true);
    });

    it('returns true for .zip extension even with wrong MIME type', () => {
      const file = new File(['test'], 'export.zip', { type: 'text/plain' });
      expect(isValidZipFile(file)).toBe(true);
    });

    it('returns false for non-ZIP files', () => {
      const file = new File(['test'], 'document.pdf', {
        type: 'application/pdf',
      });
      expect(isValidZipFile(file)).toBe(false);
    });

    it('returns false for image files', () => {
      const file = new File(['test'], 'image.png', { type: 'image/png' });
      expect(isValidZipFile(file)).toBe(false);
    });

    it('returns false for video files', () => {
      const file = new File(['test'], 'video.mp4', { type: 'video/mp4' });
      expect(isValidZipFile(file)).toBe(false);
    });
  });

  describe('formatBytes', () => {
    it('formats 0 bytes correctly', () => {
      expect(formatBytes(0)).toBe('0 Bytes');
    });

    it('formats bytes correctly', () => {
      expect(formatBytes(500)).toBe('500 Bytes');
    });

    it('formats kilobytes correctly', () => {
      expect(formatBytes(1024)).toBe('1 KB');
      expect(formatBytes(1536)).toBe('1.5 KB');
    });

    it('formats megabytes correctly', () => {
      expect(formatBytes(1048576)).toBe('1 MB');
      expect(formatBytes(52428800)).toBe('50 MB');
    });

    it('formats gigabytes correctly', () => {
      expect(formatBytes(1073741824)).toBe('1 GB');
    });

    it('respects decimal places parameter', () => {
      expect(formatBytes(1536, 0)).toBe('2 KB');
      expect(formatBytes(1536, 1)).toBe('1.5 KB');
      expect(formatBytes(1536, 3)).toBe('1.5 KB');
    });

    it('formats MAX_FILE_SIZE (500MB) correctly', () => {
      expect(formatBytes(MAX_FILE_SIZE)).toBe('500 MB');
    });
  });

  describe('Constants', () => {
    it('MAX_FILE_SIZE is 500MB', () => {
      expect(MAX_FILE_SIZE).toBe(500 * 1024 * 1024);
    });

    it('ALLOWED_FILE_TYPES includes common ZIP MIME types', () => {
      expect(ALLOWED_FILE_TYPES).toContain('application/zip');
      expect(ALLOWED_FILE_TYPES).toContain('application/x-zip-compressed');
      expect(ALLOWED_FILE_TYPES).toContain('application/octet-stream');
    });

    it('ALLOWED_EXTENSIONS only includes .zip', () => {
      expect(ALLOWED_EXTENSIONS).toEqual(['.zip']);
    });
  });
});
