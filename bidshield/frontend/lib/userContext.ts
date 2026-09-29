'use client';
import { createContext, useContext } from 'react';
import { Role } from './permissions';

export interface CurrentUser {
  id: number;
  username: string;
  full_name: string;
  email: string;
  role: Role | string;
  tenant_id: number;
  organization?: string;
  is_active: boolean;
}

export const UserContext = createContext<CurrentUser | null>(null);

export function useCurrentUser(): CurrentUser | null {
  return useContext(UserContext);
}
