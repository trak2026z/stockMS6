import { BaseEntity, Column, Entity, PrimaryGeneratedColumn } from "typeorm";

@Entity({ name: "request_attempt_log" })
export class RequestAttemptLog extends BaseEntity {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column({ type: "timestamptz" })
  timestamp!: Date;

  @Column({ type: "integer" })
  userId!: number;

  @Column({ type: "varchar" })
  userPersona!: string;

  @Column({ type: "boolean" })
  isBlocked!: boolean;

  @Column({ type: "varchar" })
  endpointUrl!: string;

  @Column({ type: "varchar" })
  apiMethod!: string;

  @Column({ type: "varchar", nullable: true })
  requestId?: string;
}
