// 训练计划数据
const trainingPlans = {
  "计划A": {
    "id": "plan-a",
    "name": "常规力量训练日计划（35分钟版）",
    "category": "regular",
    "difficulty": "中级",
    "duration": 35,
    "description": "每周1-2次，与跑步日分开，全面提升基础力量、肌肉耐力、关节稳定性，从根本上预防损伤并提升运动表现。",
    "segments": [
      {
        "name": "热身",
        "duration": 5,
        "exercises": [
          {
            "id": "exercise-001",
            "sets": 1,
            "reps": 10,
            "rest": 0
          },
          {
            "id": "exercise-002",
            "sets": 1,
            "reps": 10,
            "repsLabel": "前后各10步",
            "rest": 0
          },
          {
            "id": "exercise-003",
            "sets": 1,
            "reps": 7,
            "repsLabel": "6-8",
            "rest": 0
          }
        ]
      },
      {
        "name": "主体训练",
        "duration": 25,
        "exercises": [
          {
            "id": "exercise-004",
            "sets": 3,
            "time": 53,
            "timeLabel": "45-60秒",
            "rest": 60
          },
          {
            "id": "exercise-005",
            "sets": 3,
            "reps": 18,
            "repsLabel": "15-20次",
            "rest": 45
          },
          {
            "id": "exercise-006",
            "sets": 3,
            "reps": 11,
            "repsLabel": "每边10-12次",
            "rest": 60
          },
          {
            "id": "exercise-007",
            "sets": 3,
            "reps": 18,
            "repsLabel": "每边15-20次",
            "rest": 45
          },
          {
            "id": "exercise-008",
            "sets": 3,
            "time": 60,
            "timeLabel": "60秒",
            "rest": 45
          },
          {
            "id": "exercise-009",
            "sets": 3,
            "reps": "力竭",
            "repsLabel": "力竭次数",
            "rest": 60
          }
        ]
      },
      {
        "name": "爆发力（选做）",
        "duration": 5,
        "exercises": [
          {
            "id": "exercise-010",
            "sets": 2,
            "reps": 9,
            "repsLabel": "每边8-10次",
            "rest": 90
          },
          {
            "id": "exercise-011",
            "sets": 2,
            "time": 30,
            "timeLabel": "30秒",
            "rest": 60
          }
        ]
      },
      {
        "name": "拉伸放松",
        "duration": 5,
        "exercises": [
          {
            "id": "exercise-012",
            "sets": 2,
            "time": 30,
            "timeLabel": "每边30秒",
            "rest": 0
          },
          {
            "id": "exercise-013",
            "sets": 2,
            "time": 30,
            "timeLabel": "每边30秒",
            "rest": 0
          },
          {
            "id": "exercise-014",
            "sets": 2,
            "time": 30,
            "timeLabel": "每边30秒",
            "rest": 0
          }
        ]
      }
    ]
  },
  "计划A15": {
    "id": "plan-a-15",
    "name": "常规力量训练日计划（15分钟版）",
    "category": "regular",
    "difficulty": "初级",
    "duration": 15,
    "description": "时间有限时的高效训练方案，快速提升基础力量和关节稳定性。",
    "segments": [
      {
        "name": "热身",
        "duration": 2,
        "exercises": [
          {
            "id": "exercise-015",
            "sets": 1,
            "time": 45,
            "timeLabel": "45秒",
            "rest": 0
          },
          {
            "id": "exercise-002",
            "sets": 1,
            "reps": 7,
            "repsLabel": "前后各6-8步",
            "rest": 0
          }
        ]
      },
      {
        "name": "主体训练",
        "duration": 10,
        "exercises": [
          {
            "id": "exercise-004",
            "sets": 3,
            "time": 45,
            "timeLabel": "45秒",
            "rest": 60
          },
          {
            "id": "exercise-016",
            "sets": 3,
            "reps": 12,
            "repsLabel": "每边12次",
            "rest": 60
          },
          {
            "id": "exercise-017",
            "sets": 3,
            "reps": 10,
            "repsLabel": "每边10次",
            "rest": 60
          },
          {
            "id": "exercise-006",
            "sets": 3,
            "reps": 10,
            "repsLabel": "每边10次",
            "rest": 60
          },
          {
            "id": "exercise-008",
            "sets": 3,
            "time": 45,
            "timeLabel": "45秒",
            "rest": 45
          },
          {
            "id": "exercise-018",
            "sets": 3,
            "reps": 15,
            "repsLabel": "每边15次",
            "rest": 45
          }
        ]
      },
      {
        "name": "拉伸放松",
        "duration": 3,
        "exercises": [
          {
            "id": "exercise-012",
            "sets": 1,
            "time": 30,
            "timeLabel": "每边30秒",
            "rest": 0
          },
          {
            "id": "exercise-019",
            "sets": 1,
            "time": 30,
            "timeLabel": "每边30秒",
            "rest": 0
          },
          {
            "id": "exercise-020",
            "sets": 1,
            "time": 30,
            "timeLabel": "每边30秒",
            "rest": 0
          }
        ]
      }
    ]
  },
  "计划B": {
    "id": "plan-b",
    "name": "跑后专项激活与预防计划",
    "category": "post-run",
    "difficulty": "初级",
    "duration": 15,
    "description": "每次跑步训练结束后，在身体还未完全冷却时进行，针对跑步中易疲劳和易受伤部位进行激活、强化和拉伸，加速恢复，预防劳损。",
    "segments": [
      {
        "name": "激活强化",
        "duration": 10,
        "exercises": [
          {
            "id": "exercise-021",
            "sets": 2,
            "reps": 18,
            "repsLabel": "15-20",
            "rest": 30
          },
          {
            "id": "exercise-016",
            "sets": 2,
            "reps": 14,
            "repsLabel": "每边12-15次",
            "rest": 45
          },
          {
            "id": "exercise-022",
            "sets": 2,
            "time": 38,
            "timeLabel": "每边30-45秒",
            "rest": 30
          },
          {
            "id": "exercise-023",
            "sets": 2,
            "reps": 11,
            "repsLabel": "每边10-12次",
            "rest": 30
          }
        ]
      },
      {
        "name": "重点拉伸",
        "duration": 5,
        "exercises": [
          {
            "id": "exercise-019",
            "sets": 2,
            "time": 30,
            "timeLabel": "每边30秒",
            "rest": 0
          },
          {
            "id": "exercise-014",
            "sets": 2,
            "time": 30,
            "timeLabel": "每边30秒",
            "rest": 0
          },
          {
            "id": "exercise-046",
            "sets": 2,
            "time": 30,
            "timeLabel": "每边30秒",
            "rest": 0
          },
          {
            "id": "exercise-012",
            "sets": 2,
            "time": 30,
            "timeLabel": "每边30秒",
            "rest": 0
          }
        ]
      }
    ]
  },
  "计划C": {
    "id": "plan-c",
    "name": "跑前动态热身与神经激活计划",
    "category": "pre-run",
    "difficulty": "初级",
    "duration": 11,
    "description": "每次跑步训练开始前，代替静态拉伸，提高心率、体温，动态拉伸肌肉，激活神经系统，模拟跑步动作，让身体进入'准备跑步'的状态。",
    "segments": [
      {
        "name": "一般热身",
        "duration": 3,
        "exercises": [
          {
            "id": "exercise-024",
            "sets": 1,
            "time": 45,
            "timeLabel": "45秒",
            "rest": 30
          },
          {
            "id": "exercise-001",
            "sets": 1,
            "reps": 11,
            "repsLabel": "每边10-12次",
            "rest": 0
          }
        ]
      },
      {
        "name": "动态拉伸",
        "duration": 5,
        "exercises": [
          {
            "id": "exercise-025",
            "sets": 1,
            "reps": 9,
            "repsLabel": "前后各8-10步",
            "rest": 0
          },
          {
            "id": "exercise-026",
            "sets": 1,
            "reps": 6,
            "repsLabel": "每边5-6次",
            "rest": 0
          },
          {
            "id": "exercise-027",
            "sets": 2,
            "time": 18,
            "timeLabel": "15-20秒",
            "rest": 30
          },
          {
            "id": "exercise-028",
            "sets": 2,
            "time": 18,
            "timeLabel": "15-20秒",
            "rest": 30
          }
        ]
      },
      {
        "name": "专项激活",
        "duration": 3,
        "exercises": [
          {
            "id": "exercise-029",
            "sets": 2,
            "reps": 9,
            "repsLabel": "8-10米",
            "rest": 45
          },
          {
            "id": "exercise-030",
            "sets": 2,
            "reps": 9,
            "repsLabel": "8-10米",
            "rest": 45
          },
          {
            "id": "exercise-031",
            "sets": 1,
            "reps": 7,
            "repsLabel": "5-8",
            "rest": 30
          }
        ]
      }
    ]
  },
  "计划D50": {
    "id": "plan-d-50",
    "name": "膝关节保护专项计划（50分钟版）",
    "category": "knee",
    "difficulty": "中级",
    "duration": 50,
    "description": "针对膝关节保护的专项训练计划，系统强化膝关节周围肌肉，提高关节稳定性，预防和缓解膝关节不适。",
    "segments": [
      {
        "name": "评估与激活",
        "duration": 10,
        "exercises": [
          {
            "id": "exercise-032",
            "sets": 2,
            "reps": 7,
            "repsLabel": "每边5-8次",
            "rest": 60
          },
          {
            "id": "exercise-033",
            "sets": 2,
            "reps": 7,
            "repsLabel": "每边5-8次",
            "rest": 60
          },
          {
            "id": "exercise-033",
            "sets": 2,
            "time": 38,
            "timeLabel": "30-45秒",
            "rest": 60
          },
          {
            "id": "exercise-016",
            "sets": 2,
            "reps": 14,
            "repsLabel": "每边12-15次",
            "rest": 60
          },
          {
            "id": "exercise-034",
            "sets": 1,
            "reps": 10,
            "repsLabel": "每边顺时针/逆时针各10圈",
            "rest": 0
          },
          {
            "id": "exercise-035",
            "sets": 1,
            "reps": 10,
            "repsLabel": "每边顺时针/逆时针各10圈",
            "rest": 0
          }
        ]
      },
      {
        "name": "主体强化训练",
        "duration": 25,
        "exercises": [
          {
            "id": "exercise-004",
            "sets": 3,
            "time": 53,
            "timeLabel": "45-60秒",
            "rest": 60
          },
          {
            "id": "exercise-036",
            "sets": 3,
            "reps": 11,
            "repsLabel": "每边10-12次",
            "rest": 60
          },
          {
            "id": "exercise-007",
            "sets": 3,
            "reps": 18,
            "repsLabel": "每边15-20次",
            "rest": 45
          },
          {
            "id": "exercise-037",
            "sets": 3,
            "reps": 18,
            "repsLabel": "每边15-20次",
            "rest": 45
          },
          {
            "id": "exercise-038",
            "sets": 2,
            "reps": 9,
            "repsLabel": "每边8-10次",
            "rest": 60
          },
          {
            "id": "exercise-039",
            "sets": 2,
            "reps": 11,
            "repsLabel": "每边10-12次",
            "rest": 60
          },
          {
            "id": "exercise-040",
            "sets": 2,
            "reps": 11,
            "repsLabel": "每边10-12次（或30秒/侧）",
            "rest": 45
          }
        ]
      },
      {
        "name": "整合与神经肌肉控制",
        "duration": 10,
        "exercises": [
          {
            "id": "exercise-041",
            "sets": 2,
            "time": 25,
            "timeLabel": "20-30秒",
            "rest": 60
          },
          {
            "id": "exercise-010",
            "sets": 2,
            "reps": 9,
            "repsLabel": "每边8-10次",
            "rest": 60
          },
          {
            "id": "exercise-042",
            "sets": 2,
            "reps": 13,
            "repsLabel": "10-15",
            "rest": 60
          },
          {
            "id": "exercise-043",
            "sets": 1,
            "reps": 7,
            "repsLabel": "5-8",
            "rest": 30
          },
          {
            "id": "exercise-044",
            "sets": 2,
            "reps": 13,
            "repsLabel": "每边10-15次",
            "rest": 60
          }
        ]
      },
      {
        "name": "拉伸与放松",
        "duration": 10,
        "exercises": [
          {
            "id": "exercise-012",
            "sets": 2,
            "time": 30,
            "timeLabel": "每边30秒",
            "rest": 0
          },
          {
            "id": "exercise-045",
            "sets": 2,
            "time": 30,
            "timeLabel": "每边30秒",
            "rest": 0
          },
          {
            "id": "exercise-046",
            "sets": 2,
            "time": 30,
            "timeLabel": "每边30秒",
            "rest": 0
          },
          {
            "id": "exercise-019",
            "sets": 2,
            "time": 30,
            "timeLabel": "每边30秒",
            "rest": 0
          },
          {
            "id": "exercise-047",
            "sets": 2,
            "time": 30,
            "timeLabel": "每边30秒",
            "rest": 0
          }
        ]
      }
    ]
  },
  "计划D15": {
    "id": "plan-d-15",
    "name": "膝关节保护专项计划（15分钟版）",
    "category": "knee",
    "difficulty": "初级",
    "duration": 15,
    "description": "时间有限时的膝关节保护专项训练，重点强化膝关节周围肌肉，提高关节稳定性。",
    "segments": [
      {
        "name": "动态激活",
        "duration": 3,
        "exercises": [
          {
            "id": "exercise-048",
            "sets": 1,
            "reps": 10,
            "repsLabel": "左右腿各10次",
            "rest": 0
          },
          {
            "id": "exercise-002",
            "sets": 1,
            "reps": 8,
            "repsLabel": "前后方向各8步",
            "rest": 0
          }
        ]
      },
      {
        "name": "核心力量训练",
        "duration": 10,
        "exercises": [
          {
            "id": "exercise-004",
            "sets": 3,
            "time": 45,
            "timeLabel": "45秒",
            "rest": 60
          },
          {
            "id": "exercise-016",
            "sets": 3,
            "reps": 14,
            "repsLabel": "每侧12-15次",
            "rest": 60
          },
          {
            "id": "exercise-049",
            "sets": 3,
            "reps": 18,
            "repsLabel": "每侧15-20次",
            "rest": 45
          },
          {
            "id": "exercise-006",
            "sets": 3,
            "reps": 11,
            "repsLabel": "每侧10-12次",
            "rest": 45
          }
        ]
      },
      {
        "name": "平衡与整理",
        "duration": 2,
        "exercises": [
          {
            "id": "exercise-050",
            "sets": 1,
            "time": 30,
            "timeLabel": "每侧30秒",
            "rest": 0
          },
          {
            "id": "exercise-012",
            "sets": 1,
            "time": 30,
            "timeLabel": "每侧30秒",
            "rest": 0
          },
          {
            "id": "exercise-051",
            "sets": 1,
            "time": 30,
            "timeLabel": "每侧30秒",
            "rest": 0
          }
        ]
      }
    ]
  }
};

// 导出训练计划数据
if (typeof module !== 'undefined' && module.exports) {
  module.exports = trainingPlans;
}
