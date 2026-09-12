// Shared API model types for FinFlow.

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface User {
  id: string
  username: string
  email: string
  role: 'OWNER' | 'VIEWER'
  status: string
  created_at: string
}

export interface Bank {
  id: string
  code: string
  name: string
  country: string
  logo: string | null
  statement_parser_type: string
  created_at: string
}

export interface Account {
  id: string
  user_id: string
  bank_id: string
  name: string
  masked_account_no: string | null
  account_type: string
  currency: string
  actual_balance: string
  balance_as_of: string | null
  minimum_balance: string
  include_in_allocation: boolean
  status: string
  reserved_amount: string
  planning_available: string
  created_at: string
  updated_at: string
}

export interface PaymentPlan {
  id: string
  user_id: string
  name: string
  description: string | null
  payee_name: string | null
  amount: string
  currency: string
  planned_date: string
  priority: string
  preferred_account_id: string | null
  status: string
  manual_execution_at: string | null
  manual_execution_account_id: string | null
  manual_execution_note: string | null
  bank_reference: string | null
  created_at: string
  updated_at: string
}

export interface Allocation {
  id: string
  payment_id: string
  account_id: string
  allocated_amount: string
  status: string
  algorithm_version: string
  created_at: string
}

export interface Reconciliation {
  id: string
  payment_id: string
  transaction_id: string
  total_score: number
  amount_score: number
  account_score: number
  date_score: number
  counterparty_score: number
  reference_score: number
  status: string
  confirmed_by: string | null
  confirmed_at: string | null
  created_at: string
}

export interface ForecastDay {
  date: string
  starting_balance: string
  expected_income: string
  expected_expense: string
  ending_balance: string
  below_minimum: boolean
}

export interface ForecastResponse {
  accounts: Record<string, ForecastDay[]>
  aggregate: ForecastDay[]
  warnings: Array<{
    account_id: string
    date: string
    projected_balance: string
    minimum_balance: string
  }>
}

export interface AuditLog {
  id: string
  user_id: string
  action: string
  resource_type: string
  resource_id: string | null
  before_data: unknown
  after_data: unknown
  trace_id: string | null
  created_at: string
}

export interface ErrorBody {
  code: string
  message: string
  trace_id: string | null
}

export type StatementImportStatus =
  | 'UPLOADED'
  | 'QUEUED'
  | 'PARSING'
  | 'PARTIAL_SUCCESS'
  | 'SUCCESS'
  | 'FAILED'

export interface UploadResult {
  import_id: string
  status: StatementImportStatus
  is_duplicate: boolean
  message: string
}

export interface StatementImport {
  id: string
  account_id: string
  original_filename: string
  file_type: string
  status: StatementImportStatus
  statement_start_date: string | null
  statement_end_date: string | null
  total_rows: number
  success_rows: number
  failed_rows: number
  created_at: string
  completed_at: string | null
}

export interface ImportError {
  id: string
  row_number: number | null
  field: string | null
  raw_value: string | null
  error_code: string
  message: string
}

export interface StatementImportDetail {
  import_record: StatementImport
  errors: ImportError[]
}
