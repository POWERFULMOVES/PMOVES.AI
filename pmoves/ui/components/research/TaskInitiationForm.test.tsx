/* ═══════════════════════════════════════════════════════════════════════════
   Task Initiation Form Component Tests
   Tests form validation and options for Deep Research tasks
   ═══════════════════════════════════════════════════════════════════════════ */

import { render, screen, fireEvent } from '@testing-library/react';
import { TaskInitiationForm } from './TaskInitiationForm';

describe('TaskInitiationForm', () => {
  const mockOnSubmit = jest.fn();
  const mockNotebooks = [
    { id: 'nb1', name: 'Research Notes' },
    { id: 'nb2', name: 'Project Ideas' },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Query validation', () => {
    it('should validate non-empty query', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} />);

      const submitButton = screen.getByText('Start Research');
      expect(submitButton).toBeDisabled();

      const textarea = screen.getByLabelText('Research Question');
      expect(textarea).toBeInTheDocument();
    });

    it('should enable submit when query has content', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} />);

      const textarea = screen.getByLabelText('Research Question');
      fireEvent.change(textarea, { target: { value: 'Test query' } });

      const submitButton = screen.getByText('Start Research');
      expect(submitButton).not.toBeDisabled();
    });

    it('should trim whitespace from query', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} />);

      const textarea = screen.getByLabelText('Research Question');
      fireEvent.change(textarea, { target: { value: '  padded query  ' } });

      const form = screen.getByText('Start Research').closest('form');
      fireEvent.submit(form!);

      expect(mockOnSubmit).toHaveBeenCalledWith('padded query', expect.any(Object));
    });

    it('should not submit empty query with only spaces', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} />);

      const textarea = screen.getByLabelText('Research Question');
      fireEvent.change(textarea, { target: { value: '   ' } });

      const form = screen.getByText('Start Research').closest('form');
      fireEvent.submit(form!);

      expect(mockOnSubmit).not.toHaveBeenCalled();
    });
  });

  describe('Expand/collapse options panel', () => {
    it('should be collapsed by default', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} />);

      // Options should not be visible
      expect(screen.queryByLabelText('Execution Mode')).not.toBeInTheDocument();
      expect(screen.queryByText(/Max Iterations:/)).not.toBeInTheDocument();
    });

    it('should expand when toggle button clicked', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} />);

      const toggleButton = screen.getByLabelText('Expand options');
      fireEvent.click(toggleButton);

      expect(screen.getByLabelText('Execution Mode')).toBeInTheDocument();
      expect(screen.getByText(/Max Iterations:/)).toBeInTheDocument();
    });

    it('should rotate chevron icon when expanded', () => {
      const { container } = render(<TaskInitiationForm onSubmit={mockOnSubmit} />);

      const chevron = container.querySelector('svg');
      expect(chevron).not.toHaveClass('rotate-180');

      fireEvent.click(screen.getByLabelText('Expand options'));

      expect(chevron).toHaveClass('rotate-180');
    });
  });

  describe('Mode selection', () => {
    it('should select mode from dropdown', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} />);

      fireEvent.click(screen.getByLabelText('Expand options'));

      const select = screen.getByLabelText('Execution Mode');
      expect(select).toHaveValue('tensorzero'); // Default

      fireEvent.change(select, { target: { value: 'openrouter' } });
      expect(select).toHaveValue('openrouter');

      fireEvent.change(select, { target: { value: 'local' } });
      expect(select).toHaveValue('local');

      fireEvent.change(select, { target: { value: 'hybrid' } });
      expect(select).toHaveValue('hybrid');
    });

    it('should show all mode options', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} />);

      fireEvent.click(screen.getByLabelText('Expand options'));

      expect(screen.getByText('TensorZero - GPU-accelerated local models')).toBeInTheDocument();
      expect(screen.getByText('OpenRouter - Cloud API gateway')).toBeInTheDocument();
      expect(screen.getByText('Local - CPU-only local models')).toBeInTheDocument();
      expect(screen.getByText('Hybrid - Automatic fallback')).toBeInTheDocument();
    });
  });

  describe('Max iterations slider', () => {
    it('should update max iterations slider (3-30)', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} />);

      fireEvent.click(screen.getByLabelText('Expand options'));

      // Default value
      expect(screen.getByText('Max Iterations: 10')).toBeInTheDocument();

      const slider = screen.getByLabelText(/Max Iterations:/);
      fireEvent.change(slider, { target: { value: '15' } });

      expect(screen.getByText('Max Iterations: 15')).toBeInTheDocument();
    });

    it('should enforce min value of 3', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} />);

      fireEvent.click(screen.getByLabelText('Expand options'));

      const slider = screen.getByLabelText(/Max Iterations:/);
      expect(slider).toHaveAttribute('min', '3');
    });

    it('should enforce max value of 30', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} />);

      fireEvent.click(screen.getByLabelText('Expand options'));

      const slider = screen.getByLabelText(/Max Iterations:/);
      expect(slider).toHaveAttribute('max', '30');
    });

    it('should show range labels', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} />);

      fireEvent.click(screen.getByLabelText('Expand options'));

      expect(screen.getByText('3 (fast)')).toBeInTheDocument();
      expect(screen.getByText('30 (thorough)')).toBeInTheDocument();
    });
  });

  describe('Priority slider', () => {
    it('should update priority slider (1-10)', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} />);

      fireEvent.click(screen.getByLabelText('Expand options'));

      // Default value
      expect(screen.getByText('Priority: 5')).toBeInTheDocument();

      const slider = screen.getByLabelText(/Priority:/);
      fireEvent.change(slider, { target: { value: '8' } });

      expect(screen.getByText('Priority: 8')).toBeInTheDocument();
    });

    it('should enforce min value of 1', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} />);

      fireEvent.click(screen.getByLabelText('Expand options'));

      const slider = screen.getByLabelText(/Priority:/);
      expect(slider).toHaveAttribute('min', '1');
    });

    it('should enforce max value of 10', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} />);

      fireEvent.click(screen.getByLabelText('Expand options'));

      const slider = screen.getByLabelText(/Priority:/);
      expect(slider).toHaveAttribute('max', '10');
    });

    it('should show range labels', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} />);

      fireEvent.click(screen.getByLabelText('Expand options'));

      expect(screen.getByText('1 (low)')).toBeInTheDocument();
      expect(screen.getByText('10 (urgent)')).toBeInTheDocument();
    });
  });

  describe('Notebook selection', () => {
    it('should show notebook dropdown when notebooks provided', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} notebooks={mockNotebooks} />);

      fireEvent.click(screen.getByLabelText('Expand options'));

      // Label includes "(optional)" suffix
      expect(screen.getByLabelText('Publish to Notebook (optional)')).toBeInTheDocument();
    });

    it('should list all notebooks', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} notebooks={mockNotebooks} />);

      fireEvent.click(screen.getByLabelText('Expand options'));

      expect(screen.getByText('No notebook')).toBeInTheDocument();
      expect(screen.getByText('Research Notes')).toBeInTheDocument();
      expect(screen.getByText('Project Ideas')).toBeInTheDocument();
    });

    it('should select notebook', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} notebooks={mockNotebooks} />);

      fireEvent.click(screen.getByLabelText('Expand options'));

      // Label includes "(optional)" suffix
      const select = screen.getByLabelText('Publish to Notebook (optional)');
      fireEvent.change(select, { target: { value: 'nb1' } });

      expect(select).toHaveValue('nb1');
    });

    it('should not show notebook dropdown when no notebooks', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} notebooks={[]} />);

      fireEvent.click(screen.getByLabelText('Expand options'));

      expect(screen.queryByLabelText('Publish to Notebook (optional)')).not.toBeInTheDocument();
    });
  });

  describe('Character count', () => {
    it('should show character count for query', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} />);

      const textarea = screen.getByLabelText('Research Question');

      expect(screen.getByText('0 / 1000')).toBeInTheDocument();

      fireEvent.change(textarea, { target: { value: 'Test query' } });

      expect(screen.getByText('10 / 1000')).toBeInTheDocument();
    });

    it('should enforce max length of 1000', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} />);

      const textarea = screen.getByLabelText('Research Question');
      expect(textarea).toHaveAttribute('maxLength', '1000');
    });
  });

  describe('Form submission', () => {
    it('should call onSubmit with query and default options', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} />);

      const textarea = screen.getByLabelText('Research Question');
      fireEvent.change(textarea, { target: { value: 'What is quantum computing?' } });

      fireEvent.click(screen.getByText('Start Research'));

      expect(mockOnSubmit).toHaveBeenCalledWith('What is quantum computing?', {
        mode: 'tensorzero',
        maxIterations: 10,
        priority: 5,
        notebookId: undefined,
      });
    });

    it('should call onSubmit with custom options', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} notebooks={mockNotebooks} />);

      // Expand options
      fireEvent.click(screen.getByLabelText('Expand options'));

      // Change options
      fireEvent.change(screen.getByLabelText('Execution Mode'), { target: { value: 'openrouter' } });
      fireEvent.change(screen.getByLabelText(/Max Iterations:/), { target: { value: '15' } });
      fireEvent.change(screen.getByLabelText(/Priority:/), { target: { value: '8' } });
      fireEvent.change(screen.getByLabelText('Publish to Notebook (optional)'), { target: { value: 'nb1' } });

      // Enter query
      const textarea = screen.getByLabelText('Research Question');
      fireEvent.change(textarea, { target: { value: 'Test research' } });

      fireEvent.click(screen.getByText('Start Research'));

      expect(mockOnSubmit).toHaveBeenCalledWith('Test research', {
        mode: 'openrouter',
        maxIterations: 15,
        priority: 8,
        notebookId: 'nb1',
      });
    });
  });

  describe('Form clearing', () => {
    it('should show clear button when query has content', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} />);

      expect(screen.queryByText('Clear')).not.toBeInTheDocument();

      const textarea = screen.getByLabelText('Research Question');
      fireEvent.change(textarea, { target: { value: 'Test' } });

      expect(screen.getByText('Clear')).toBeInTheDocument();
    });

    it('should clear form when clear button clicked', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} />);

      const textarea = screen.getByLabelText('Research Question');
      fireEvent.change(textarea, { target: { value: 'Test query' } });

      fireEvent.click(screen.getByText('Clear'));

      expect(textarea).toHaveValue('');
    });
  });

  describe('Loading state', () => {
    it('should show loading state when loading prop is true', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} loading={true} />);

      // Button contains the loading text in a span
      const button = screen.getByRole('button', { name: /Starting Research/i });
      expect(button).toBeInTheDocument();
      expect(button).toBeDisabled();
    });

    it('should disable textarea during loading', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} loading={true} />);

      const textarea = screen.getByLabelText('Research Question');
      expect(textarea).toBeDisabled();
    });

    it('should disable options during loading', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} loading={true} />);

      fireEvent.click(screen.getByLabelText('Expand options'));

      expect(screen.getByLabelText('Execution Mode')).toBeDisabled();
      expect(screen.getByLabelText(/Max Iterations:/)).toBeDisabled();
      expect(screen.getByLabelText(/Priority:/)).toBeDisabled();
    });

    it('should disable clear button during loading', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} loading={true} />);

      const textarea = screen.getByLabelText('Research Question');
      fireEvent.change(textarea, { target: { value: 'Test' } });

      const clearButton = screen.getByText('Clear');
      expect(clearButton).toBeDisabled();
    });
  });

  describe('Form submit prevention', () => {
    it('should prevent default form submission', () => {
      render(<TaskInitiationForm onSubmit={mockOnSubmit} />);

      const textarea = screen.getByLabelText('Research Question');
      fireEvent.change(textarea, { target: { value: 'Test query' } });

      const form = screen.getByText('Start Research').closest('form');
      const submitEvent = new Event('submit', { bubbles: true, cancelable: true });
      Object.assign(submitEvent, { preventDefault: jest.fn() });

      form?.dispatchEvent(submitEvent);

      expect(submitEvent.preventDefault).toHaveBeenCalled();
    });
  });
});
