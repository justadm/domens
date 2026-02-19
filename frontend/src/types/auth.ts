export type CapabilityMap = Record<string, boolean>;

export interface AuthUser {
  telegram_user_id: string;
  username?: string | null;
  first_name?: string | null;
  locale?: string | null;
  is_admin?: boolean;
  capabilities?: CapabilityMap;
  permissions?: string[];
}

export interface AuthMeResponse {
  authenticated: boolean;
  user: AuthUser | null;
}

export interface NavItem {
  key: string;
  label: string;
  to: string;
  requires?: string;
}
