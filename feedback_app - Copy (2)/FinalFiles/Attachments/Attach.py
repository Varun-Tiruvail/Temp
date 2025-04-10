def plot_pie_chart(self, ax, data, title):
    """Helper function to plot individual pie charts"""
    # Initialize annotation for this axis
    ax.annot = ax.annotate("", xy=(0,0), xytext=(20,20),
                         textcoords="offset points",
                         bbox=dict(boxstyle="round", fc="white", alpha=0.8),
                         arrowprops=dict(arrowstyle="->"))
    ax.annot.set_visible(False)

    option_counts = data['response_value'].value_counts().sort_index()
    all_options = pd.Series([0]*4, index=[1,2,3,4])
    
    for idx, count in option_counts.items():
        if 1 <= idx <= 4:
            all_options[idx] = count
    
    # Get option labels from questions_df
    question_row = self.questions_df[self.questions_df['QuestionID'] == data['QuestionID'].iloc[0]]
    option_labels = [f"{i+1}: {question_row[f'Option{i+1}'].values[0]}" for i in range(4)]
    
    wedges, texts, autotexts = ax.pie(
        all_options,
        labels=None,
        autopct='%1.1f%%',
        startangle=90,
        colors=cm.viridis(np.linspace(0.2, 0.8, 4)),
        wedgeprops={'linewidth': 1, 'edgecolor': 'white'},
        textprops={'color': 'black', 'fontsize': 9}  # Changed to visible text color
    )
    
    # Store references
    ax.wedges = wedges
    ax.labels = option_labels  # Store full labels for legend
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.axis('equal')

    return wedges  # Return wedges for legend creation

def update_question_analysis(self, question_text):
    if self.merged_data is None or not question_text:
        return
    
    try:
        self.question_canvas.fig.clf()
        ax1 = self.question_canvas.fig.add_subplot(121)
        ax2 = self.question_canvas.fig.add_subplot(122)

        # Plot charts and get wedges
        wedges1 = self.plot_pie_chart(ax1, your_data, "Your Responses")
        wedges2 = self.plot_pie_chart(ax2, team_data, "Team Responses")

        # Create unified legend using first plot's wedges
        handles = wedges1
        labels = [self.questions_df[self.questions_df['QuestionID'] == question_id]
                  [f'Option{i+1}'].values[0] for i in range(4)]

        # Add legend below both charts
        self.question_canvas.fig.legend(
            handles, labels,
            title="Response Options:",
            loc='lower center',
            ncol=2,
            bbox_to_anchor=(0.5, -0.1),
            fontsize=9
        )

        # Adjust layout
        self.question_canvas.fig.subplots_adjust(bottom=0.3, wspace=0.4)
        self.question_canvas.fig.suptitle(
            f"Question Analysis: {question_text}", 
            y=1.02,
            fontsize=14,
            fontweight='bold'
        )
        self.question_canvas.draw()
    except Exception as e:
        QMessageBox.warning(self, "Error", f"Error updating question analysis: {str(e)}")