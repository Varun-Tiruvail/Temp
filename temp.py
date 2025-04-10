def plot_pie_chart(self, ax, data, title):
    """Helper function to plot pie charts with dynamic options"""
    ax.annot = ax.annotate("", xy=(0,0), xytext=(20,20),
                         textcoords="offset points",
                         bbox=dict(boxstyle="round", fc="white", alpha=0.8),
                         arrowprops=dict(arrowstyle="->"))
    ax.annot.set_visible(False)
    
    # Get question ID from the first row (assuming all rows are same question)
    if data.empty:
        return None, None
    
    q_id = data.iloc[0]['question_id']
    question_row = self.questions_df[self.questions_df['QuestionID'] == q_id].iloc[0]
    
    # Count how many options exist for this question
    num_options = 0
    while f'Option{num_options+1}' in question_row and pd.notna(question_row[f'Option{num_options+1}']):
        num_options += 1
    
    # Get counts for each option
    option_counts = data['response_value'].value_counts().sort_index()
    all_options = pd.Series([0]*num_options, index=range(1, num_options+1))
    
    for idx, count in option_counts.items():
        if 1 <= idx <= num_options:
            all_options[idx] = count
    
    # Get option labels
    option_labels = [question_row[f'Option{i+1}'] for i in range(num_options)]
    
    # Plot pie chart
    wedges, texts, autotexts = ax.pie(
        all_options,
        labels=None,
        autopct=lambda p: f'{p:.1f}%' if p > 0 else '',
        startangle=90,
        colors=cm.viridis(np.linspace(0.2, 0.8, num_options)),
        wedgeprops={'linewidth': 1, 'edgecolor': 'white'},
        textprops={'color': 'black', 'fontsize': 8},
        pctdistance=0.75
    )
    
    # Store references
    ax.wedges = wedges
    ax.labels = [f"{i+1}: {option_labels[i]}" for i in range(num_options)]
    ax.set_title(title, fontsize=11, pad=20)
    ax.axis('equal')
    
    return wedges, all_options

def create_lm_feedback_page(self):
    """Create the tabbed LM feedback interface with dynamic options"""
    lm_page = QWidget()
    lm_layout = QVBoxLayout(lm_page)
    
    self.lm_tabs = QTabWidget()
    self.lm_responses = {}
    
    for category in self.questions_df['Category'].unique():
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        container = QWidget()
        layout = QVBoxLayout(container)
        
        category_questions = self.questions_df[self.questions_df['Category'] == category]
        
        for _, row in category_questions.iterrows():
            q_id = row['QuestionID']
            question_text = row['Question']
            
            group_box = QGroupBox(question_text)
            group_layout = QVBoxLayout()
            
            option_group = QButtonGroup(self)
            self.lm_responses[q_id] = None
            
            # Dynamically find all options (Option1, Option2, etc.)
            options = []
            i = 1
            while f'Option{i}' in row and pd.notna(row[f'Option{i}']):
                options.append((i, row[f'Option{i}']))  # (value, text)
                i += 1
            
            for value, option_text in options:
                radio = QRadioButton(option_text)
                radio.setObjectName(f"lm_{q_id}_{value}")
                radio.toggled.connect(self.on_lm_radio_toggled)
                option_group.addButton(radio)
                group_layout.addWidget(radio)
            
            group_box.setLayout(group_layout)
            layout.addWidget(group_box)
        
        scroll.setWidget(container)
        self.lm_tabs.addTab(scroll, category)
    
    lm_layout.addWidget(self.lm_tabs)
    self.stacked_widget.addWidget(lm_page)