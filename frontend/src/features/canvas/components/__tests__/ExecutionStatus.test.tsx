/**
 * ExecutionStatus component tests.
 */
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const mockExecute = vi.fn();
const mockPost = vi.fn();

vi.mock("../../hooks/useExecution", () => ({
  useExecution: vi.fn(),
}));

vi.mock("@/shared/query-engine/client", () => ({
  apiClient: { post: (...args: unknown[]) => mockPost(...args) },
}));

import { useExecution } from "../../hooks/useExecution";
import ExecutionStatus from "../ExecutionStatus";

const mockedUseExecution = vi.mocked(useExecution);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ExecutionStatus", () => {
  it("renders Run button when idle", () => {
    mockedUseExecution.mockReturnValue({
      execute: mockExecute,
      isExecuting: false,
      status: null,
      error: null,
    });

    render(<ExecutionStatus workflowId="wf-1" />);
    expect(screen.getByRole("button", { name: "Run" })).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
  });

  it("calls execute on Run button click", () => {
    mockedUseExecution.mockReturnValue({
      execute: mockExecute,
      isExecuting: false,
      status: null,
      error: null,
    });

    render(<ExecutionStatus workflowId="wf-1" />);
    fireEvent.click(screen.getByRole("button", { name: "Run" }));
    expect(mockExecute).toHaveBeenCalled();
  });

  it("shows Cancel button and Running status when executing", () => {
    mockedUseExecution.mockReturnValue({
      execute: mockExecute,
      isExecuting: true,
      status: {
        id: "exec-1",
        workflow_id: "wf-1",
        status: "running",
        started_at: null,
        completed_at: null,
        node_statuses: {},
      },
      error: null,
    });

    render(<ExecutionStatus workflowId="wf-1" />);
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    expect(screen.getByText("Running...")).toBeInTheDocument();
  });

  it("calls cancel endpoint when Cancel is clicked", () => {
    mockedUseExecution.mockReturnValue({
      execute: mockExecute,
      isExecuting: true,
      status: {
        id: "exec-1",
        workflow_id: "wf-1",
        status: "running",
        started_at: null,
        completed_at: null,
        node_statuses: {},
      },
      error: null,
    });

    render(<ExecutionStatus workflowId="wf-1" />);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockPost).toHaveBeenCalledWith("/api/v1/executions/exec-1/cancel");
  });

  it("shows success indicator on completed status", () => {
    mockedUseExecution.mockReturnValue({
      execute: mockExecute,
      isExecuting: false,
      status: {
        id: "exec-1",
        workflow_id: "wf-1",
        status: "completed",
        started_at: null,
        completed_at: null,
        node_statuses: {},
      },
      error: null,
    });

    render(<ExecutionStatus workflowId="wf-1" />);
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run" })).toBeEnabled();
  });

  it("shows error indicator on failed status", () => {
    mockedUseExecution.mockReturnValue({
      execute: mockExecute,
      isExecuting: false,
      status: {
        id: "exec-1",
        workflow_id: "wf-1",
        status: "failed",
        started_at: null,
        completed_at: null,
        node_statuses: {},
      },
      error: new Error("Query timeout"),
    });

    render(<ExecutionStatus workflowId="wf-1" />);
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("Query timeout")).toBeInTheDocument();
  });

  it("shows cancelled indicator on cancelled status", () => {
    mockedUseExecution.mockReturnValue({
      execute: mockExecute,
      isExecuting: false,
      status: {
        id: "exec-1",
        workflow_id: "wf-1",
        status: "cancelled",
        started_at: null,
        completed_at: null,
        node_statuses: {},
      },
      error: null,
    });

    render(<ExecutionStatus workflowId="wf-1" />);
    expect(screen.getByText("Cancelled")).toBeInTheDocument();
  });

  it("passes workflowId to useExecution", () => {
    mockedUseExecution.mockReturnValue({
      execute: mockExecute,
      isExecuting: false,
      status: null,
      error: null,
    });

    render(<ExecutionStatus workflowId="wf-42" />);
    expect(mockedUseExecution).toHaveBeenCalledWith("wf-42");
  });
});
