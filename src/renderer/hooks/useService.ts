import { useContext } from "react";
import { ServiceContext, type ServiceContextType } from "../providers/ServiceProvider";

export function useService(): ServiceContextType {
  const ctx = useContext(ServiceContext);
  if (!ctx) throw new Error("useService must be used within ServiceProvider");
  return ctx;
}
