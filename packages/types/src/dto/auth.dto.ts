export interface LoginRequest {
  email: string;
  password: string;
  /** Si true, el refresh y la cookie usan el TTL extendido (~30 días). */
  remember_me?: boolean;
}

export interface RegisterRequest {
  email: string;
  password: string;
  display_name: string;
}

export interface RefreshRequest {
  refresh_token: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}
