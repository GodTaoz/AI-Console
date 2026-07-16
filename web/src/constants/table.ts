export const DEFAULT_TABLE_PAGE_SIZE = 10

export function paginationFor(itemCount: number, page?: number) {
  if (itemCount <= DEFAULT_TABLE_PAGE_SIZE) return false
  return {
    ...(page === undefined ? {} : { page }),
    pageSize: DEFAULT_TABLE_PAGE_SIZE,
    showSizePicker: false,
  }
}
