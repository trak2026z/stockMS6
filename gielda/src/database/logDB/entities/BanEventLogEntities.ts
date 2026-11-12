import { BaseEntity, Column, Entity, PrimaryGeneratedColumn } from "typeorm";

@Entity({ name: "ban_event_log" })
export class BanEventLog extends BaseEntity {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column({ type: "timestamptz" })
  banStartedAt!: Date;

  @Column({ type: "timestamptz" })
  banExpiresAt!: Date;

  @Column({ type: "integer" })
  userId!: number;

  @Column({ type: "varchar" })
  userPersona!: string;

  @Column({ type: "varchar", nullable: true })
  requestId?: string;

  @Column({ type: "integer" })
  banDurationSeconds!: number;
}
