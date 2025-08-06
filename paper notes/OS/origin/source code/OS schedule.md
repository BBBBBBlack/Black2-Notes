# 进程调度器

[源码解读](http://www.wowotech.net/process_management/448.html)

## 调度初始化

### **[sched_fork()](https://elixir.bootlin.com/linux/v4.18.20/source/kernel/sched/core.c)**

——在 **进程创建（fork or clone）**时,为新进程分配必要的调度相关资源，并对调度策略、优先级、CPU 核心等进行初始化

do_fork()---->_do_fork()---->copy_process()---->sched_fork()

```c
/*
 * fork()/clone()-time setup:
 */
int sched_fork(unsigned long clone_flags, struct task_struct *p)
{
	unsigned long flags;
	int cpu = get_cpu();

	__sched_fork(clone_flags, p);
	/*
	 * We mark the process as NEW here. This guarantees that
	 * nobody will actually run it, and a signal or other external
	 * event cannot wake it up and insert it on the runqueue either.
	 * 首次创建的进程设为TASK_NEW状态
     * 确保仍在初始化阶段，不会唤醒，也不会丢到ready queue中
	 */
	p->state = TASK_NEW;

	/*
	 * Make sure we do not leak PI boosting priority to the child.
	 * 继承其父进程的优先级
	 */
	p->prio = current->normal_prio;

	/*
	 * Revert to default priority/policy on fork if requested.
	 */
	if (unlikely(p->sched_reset_on_fork)) {
		if (task_has_dl_policy(p) || task_has_rt_policy(p)) {
			p->policy = SCHED_NORMAL;
			p->static_prio = NICE_TO_PRIO(0);
			p->rt_priority = 0;
		} else if (PRIO_TO_NICE(p->static_prio) < 0)
			p->static_prio = NICE_TO_PRIO(0);

		p->prio = p->normal_prio = __normal_prio(p);
		set_load_weight(p, false);

		/*
		 * We don't need the reset flag anymore after the fork. It has
		 * fulfilled its duty:
		 */
		p->sched_reset_on_fork = 0;
	}
```
#### 调度类

|      调度类      |      描述      |         调度策略          |
| :--------------: | :------------: | :-----------------------: |
|  dl_sched_class  | deadline调度器 |      SCHED_DEADLINE       |
|  rt_sched_class  |   实时调度器   |   SCHED_FIFO、SCHED_RR    |
| fair_sched_class | 完全公平调度器 | SCHED_NORMAL、SCHED_BATCH |
| idle_sched_class |   idle task    |        SCHED_IDLE         |

```c
    /*
     * 选择调度类
     */
    // 不允许 fork 一个 Deadline 进程
	if (dl_prio(p->prio)) {
        // 释放当前 CPU 的绑定
		put_cpu();
		return -EAGAIN;
    // 是否为实时优先级
	} else if (rt_prio(p->prio)) {
        // 设定调度类为实时调度类
		p->sched_class = &rt_sched_class;
	} else {
        // 设定调度类为普通调度类
		p->sched_class = &fair_sched_class;
	}
```
每一个进程都对应一种调度策略，每一种调度策略又对应一种调度类（每一个调度类可以对应多种调度策略）——在每个进程中用`p->sched_class`字段标识其自身的调度类

* 常见调度策略
  * fair_sched_class
    * SCHED_OTHER（CFS调度器）：标准的时间片轮转调度算法
    * SCHED_BATCH（批处理）：为了提高系统整体性能而设计的调度策略，在CPU空闲时运行批处理任务
  * rt_sched_class
    * SCHED_FIFO（实时先进先出）：按照优先级进行调度，直到任务完成或者被更高优先级任务抢占
    * SCHED_RR（实时轮转）：按照优先级进行调度，每个任务都有一个固定的时间片来执行，超过时间片后被放到队列尾部继续等待
  * idle_sched_class
    * SCHED_IDLE（空闲）：只有当没有其他可运行任务时才会运行该任务

* 调度类调度操作接口表

  ```c
  struct sched_class {
  	const struct sched_class *next;
  
  	void (*enqueue_task) (struct rq *rq, struct task_struct *p, int flags);
  	void (*dequeue_task) (struct rq *rq, struct task_struct *p, int flags);
  	void (*yield_task)   (struct rq *rq);
  	bool (*yield_to_task)(struct rq *rq, struct task_struct *p, bool preempt);
  
  	void (*check_preempt_curr)(struct rq *rq, struct task_struct *p, int flags);
  
  	/*
  	 * It is the responsibility of the pick_next_task() method that will
  	 * return the next task to call put_prev_task() on the @prev task or
  	 * something equivalent.
  	 *
  	 * May return RETRY_TASK when it finds a higher prio class has runnable
  	 * tasks.
  	 */
  	struct task_struct * (*pick_next_task)(struct rq *rq,
  					       struct task_struct *prev,
  					       struct rq_flags *rf);
  	void (*put_prev_task)(struct rq *rq, struct task_struct *p);
  
  #ifdef CONFIG_SMP
  	int  (*select_task_rq)(struct task_struct *p, int task_cpu, int sd_flag, int flags);
  	void (*migrate_task_rq)(struct task_struct *p);
  
  	void (*task_woken)(struct rq *this_rq, struct task_struct *task);
  
  	void (*set_cpus_allowed)(struct task_struct *p,
  				 const struct cpumask *newmask);
  
  	void (*rq_online)(struct rq *rq);
  	void (*rq_offline)(struct rq *rq);
  #endif
  
  	void (*set_curr_task)(struct rq *rq);
  	void (*task_tick)(struct rq *rq, struct task_struct *p, int queued);
  	void (*task_fork)(struct task_struct *p);
  	void (*task_dead)(struct task_struct *p);
  
  	/*
  	 * The switched_from() call is allowed to drop rq->lock, therefore we
  	 * cannot assume the switched_from/switched_to pair is serliazed by
  	 * rq->lock. They are however serialized by p->pi_lock.
  	 */
  	void (*switched_from)(struct rq *this_rq, struct task_struct *task);
  	void (*switched_to)  (struct rq *this_rq, struct task_struct *task);
  	void (*prio_changed) (struct rq *this_rq, struct task_struct *task,
  			      int oldprio);
  
  	unsigned int (*get_rr_interval)(struct rq *rq,
  					struct task_struct *task);
  
  	void (*update_curr)(struct rq *rq);
  
  #define TASK_SET_GROUP		0
  #define TASK_MOVE_GROUP		1
  
  #ifdef CONFIG_FAIR_GROUP_SCHED
  	void (*task_change_group)(struct task_struct *p, int type);
  #endif
  };
  ```

  `fair_sched_class`——CFS调度类调度操作的实现

  （还有其他的实现，如`rt_sched_class`：实时调度类（RT scheduling）；`dl_sched_class`：Deadline scheduling；`idle_sched_class`：空闲任务调度类）

  ```c
  /*
   * All the scheduling class methods:
   */
  const struct sched_class fair_sched_class = {
  	.next			= &idle_sched_class,
  	.enqueue_task		= enqueue_task_fair,
  	.dequeue_task		= dequeue_task_fair,
  	.yield_task		= yield_task_fair,
  	.yield_to_task		= yield_to_task_fair,
  
  	.check_preempt_curr	= check_preempt_wakeup,
  
  	.pick_next_task		= pick_next_task_fair,
  	.put_prev_task		= put_prev_task_fair,
  
  #ifdef CONFIG_SMP
  	.select_task_rq		= select_task_rq_fair,
  	.migrate_task_rq	= migrate_task_rq_fair,
  
  	.rq_online		= rq_online_fair,
  	.rq_offline		= rq_offline_fair,
  
  	.task_dead		= task_dead_fair,
  	.set_cpus_allowed	= set_cpus_allowed_common,
  #endif
  
  	.set_curr_task          = set_curr_task_fair,
  	.task_tick		= task_tick_fair,
  	.task_fork		= task_fork_fair,
  
  	.prio_changed		= prio_changed_fair,
  	.switched_from		= switched_from_fair,
  	.switched_to		= switched_to_fair,
  
  	.get_rr_interval	= get_rr_interval_fair,
  
  	.update_curr		= update_curr_fair,
  
  #ifdef CONFIG_FAIR_GROUP_SCHED
  	.task_change_group	= task_change_group_fair,
  #endif
  };
  ```

  



```c
	init_entity_runnable_average(&p->se);

	/*
	 * The child is not yet in the pid-hash so no cgroup attach races,
	 * and the cgroup is pinned to this child due to cgroup_fork()
	 * is ran before sched_fork().
	 *
	 * Silence PROVE_RCU.
	 */
	raw_spin_lock_irqsave(&p->pi_lock, flags);
	/*
	 * We're setting the CPU for the first time, we don't migrate,
	 * so use __set_task_cpu().
	 */
	__set_task_cpu(p, cpu);
	if (p->sched_class->task_fork)
		p->sched_class->task_fork(p);
```

#### [task_fork]()

* 在`sched_fork()`执行完`__set_task_cpu(p, cpu);`后，初始化sched_entity——task调度的实体，CFS通过操纵它在runqueue中的移动完成调度

  ```c
  /*
   * called on fork with the child task as argument from the parent's context
   *  - child not yet on the tasklist
   *  - preemption disabled
   */
  static void task_fork_fair(struct task_struct *p)
  {
  	struct cfs_rq *cfs_rq;
  	struct sched_entity *se = &p->se, *curr;
  	struct rq *rq = this_rq();
  	struct rq_flags rf;
  
  	rq_lock(rq, &rf);
  	update_rq_clock(rq);
      
      //  初始化子进程的 vruntime
  	cfs_rq = task_cfs_rq(current);			// 获取父进程所在的CFS运行队列
  	curr = cfs_rq->curr;					//获取父进程的sched_entity
  	if (curr) {
  		update_curr(cfs_rq);
  		se->vruntime = curr->vruntime;		// 子进程初始vruntime继承父进程
  	}
  	place_entity(cfs_rq, se, 1);			// 调整子进程在红黑树中的位置（暂时和父进程一个runqueue，等到当前进程创建完毕开始唤醒的时候，加入的runqueue不一定是现在计算基于的cpu）
  
  	if (sysctl_sched_child_runs_first && curr && entity_before(curr, se)) {
  		/*
  		 * Upon rescheduling, sched_class::put_prev_task() will place
  		 * 'current' within the tree based on its new key value.
  		 */
  		swap(curr->vruntime, se->vruntime);
  		resched_curr(rq);
  	}
  
  	se->vruntime -= cfs_rq->min_vruntime;
  	rq_unlock(rq, &rf);
  }
  ```

  



```c
	raw_spin_unlock_irqrestore(&p->pi_lock, flags);

#ifdef CONFIG_SCHED_INFO
	if (likely(sched_info_on()))
		memset(&p->sched_info, 0, sizeof(p->sched_info));
#endif
#if defined(CONFIG_SMP)
	p->on_cpu = 0;
#endif
	init_task_preempt_count(p);
#ifdef CONFIG_SMP
	plist_node_init(&p->pushable_tasks, MAX_PRIO);
	RB_CLEAR_NODE(&p->pushable_dl_tasks);
#endif

	put_cpu();
	return 0;
}
```



### [wake_up_new_task()](https://elixir.bootlin.com/linux/v4.18.20/source/kernel/fork.c#L2148)

在上一步copy_process()完成后，将唤醒新创建的线程（将新的线程放入runqueue）

```c
/*
 * wake_up_new_task - wake up a newly created task for the first time.
 *
 * This function will do some initial scheduler statistics housekeeping
 * that must be done for every newly created context, then puts the task
 * on the runqueue and wakes it.
 */
void wake_up_new_task(struct task_struct *p)
{
	struct rq_flags rf;
	struct rq *rq;

	raw_spin_lock_irqsave(&p->pi_lock, rf.flags);
    // 将任务状态设置为就绪态
	p->state = TASK_RUNNING;
#ifdef CONFIG_SMP
	/*
	 * Fork balancing, do it here and not earlier because:
	 *  - cpus_allowed can change in the fork path
	 *  - any previously selected CPU might disappear through hotplug
	 *
	 * Use __set_task_cpu() to avoid calling sched_class::migrate_task_rq,
	 * as we're not fully set-up yet.
	 */
    // 为线程选择运行的CPU
	p->recent_used_cpu = task_cpu(p);		// 获取任务当前所在的 CPU
	__set_task_cpu(p, select_task_rq(p, task_cpu(p), SD_BALANCE_FORK, 0));	// 选择合适的runqueue
#endif
	rq = __task_rq_lock(p, &rf);
	update_rq_clock(rq);
	post_init_entity_util_avg(&p->se);

    // 将线程插入选定CPU所绑定的runqueue中
	activate_task(rq, p, ENQUEUE_NOCLOCK);
	p->on_rq = TASK_ON_RQ_QUEUED;
	trace_sched_wakeup_new(p);
    // 当唤醒一个新进程的时候，此时也是一个检测抢占的机会，调用check_preempt_curr()函数检查是否满足抢占条件
	check_preempt_curr(rq, p, WF_FORK);
#ifdef CONFIG_SMP
	if (p->sched_class->task_woken) {
		/*
		 * Nothing relies on rq->lock after this, so its fine to
		 * drop it.
		 */
		rq_unpin_lock(rq, &rf);
		p->sched_class->task_woken(rq, p);
		rq_repin_lock(rq, &rf);
	}
#endif
	task_rq_unlock(rq, p, &rf);
}
```



## 周期性调度

Linux定时周期性地检查当前任务是否耗尽当前进程的时间片，并检查是否应该抢占当前进程。一般会在定时器的中断函数中，通过一层层函数调用最终到scheduler_tick()函数

```c
/*
 * This function gets called by the timer code, with HZ frequency.
 * We call it with interrupts disabled.
 */
void scheduler_tick(void)
{
	int cpu = smp_processor_id();
	struct rq *rq = cpu_rq(cpu);
	struct task_struct *curr = rq->curr;
	struct rq_flags rf;

	sched_clock_tick();

	rq_lock(rq, &rf);

	update_rq_clock(rq);
	curr->sched_class->task_tick(rq, curr, 0);
	cpu_load_update_active(rq);
	calc_global_load_tick(rq);

	rq_unlock(rq, &rf);

	perf_event_task_tick();

#ifdef CONFIG_SMP
	rq->idle_balance = idle_cpu(cpu);
	trigger_load_balance(rq);
#endif
}
```

# CFS

每个CPU绑定一个CFS runqueue

runqueue是红黑树结构——以vruntime为key，每次取出runqueue中vruntime（此刻总计运行逻辑时间——考虑权重）最小的线程执行；线程因抢占或主动让出 CPU 时重新插入红黑树

时间片由权重和调度周期动态计算

<img src="..\..\..\assets\6fb0e036bc7099a85bc496e1a0f5777b.png" alt="img" style="zoom:90%;" />
