type WorkflowTaskPaginationProps = {
  page: number
  totalPages: number
  total: number
  disabled?: boolean
  onPageChange: (page: number) => void
}

export function WorkflowTaskPagination({
  page,
  totalPages,
  total,
  disabled = false,
  onPageChange,
}: WorkflowTaskPaginationProps) {
  if (totalPages <= 1) return null
  return (
    <nav className="workflow-task-pagination" aria-label="任务分页">
      <button
        type="button"
        disabled={disabled || page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        上一页
      </button>
      <span>第 {page} / {totalPages} 页 · 共 {total} 条</span>
      <button
        type="button"
        disabled={disabled || page >= totalPages}
        onClick={() => onPageChange(page + 1)}
      >
        下一页
      </button>
    </nav>
  )
}
