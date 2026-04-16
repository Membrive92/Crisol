export interface LoginRequest {
  email: string;
  password: string;
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
